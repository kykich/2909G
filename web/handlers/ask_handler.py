"""Обработчик POST /api/ask — основная логика запроса к модели/MCP (mixin)."""
import urllib.parse

from rtk_app import config


class AskHandler:
    """Обработка POST /api/ask: выбор режима (LLM vs MCP) и обработка ответа."""

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/ask":
            return self._handle_ask()
        # Остальные POST-эндпоинты — делегируем ApiHandler.
        from .api_handler import ApiHandler
        return ApiHandler.do_POST(self)

    def _maybe_auto_compact(self):
        """Инкрементное сжатие истории: дописывает вытесненные сообщения."""
        try:
            if not self.session.should_auto_compact():
                return
            head, end = self.session.head_to_compact()
            if not head:
                return
            keep = self.session.get_compact().get("keep", config.COMPACT_KEEP)
            prev_summary = self.session.get_compact().get("summary", "")
            summary = self.agent.compact_update(prev_summary, head)
            if summary:
                self.session.apply_summary(summary, upto=end, keep=keep)
                print("[COMPACT] сжатие: +%d сообщ. -> summary (upto=%d)"
                      % (len(head), end), flush=True)
        except Exception as exc:
            print("[COMPACT] сжатие не удалось: %s" % exc, flush=True)

    def _handle_ask(self):
        """Принимает запрос пользователя и передаёт его агенту."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        question = str(data.get("question", "")).strip()
        selected = data.get("models")
        if not isinstance(selected, list) or not selected:
            selected = None

        from .. import mcp_helpers
        from ..mcp_settings import mcp_state_payload
        from .. import state as srv_state

        doska_srv = getattr(config, "COMPOSITION_DOSKA_SERVER", "doska")
        is_doska = (srv_state._ServerState.mcp_server or "") == doska_srv
        composition_active = bool(srv_state._ServerState.composition_running)
        target_is_board = is_doska or composition_active
        via_mcp = bool(srv_state._ServerState.mcp_enabled or target_is_board)

        pid, pname, pmodel, pchar, pstyle = self.session.active_profile_attrs()
        if pid and not via_mcp:
            answer_title = pname or "Персона"
            profile = {"name": pname, "character": pchar, "style": pstyle}
            if pmodel:
                selected = [{"label": pmodel}]
            elif selected is None:
                selected = None
        else:
            answer_title = None
            profile = None
            if selected is None and not via_mcp:
                return self._send_json(200, {
                    "ok": False,
                    "error": "Не выбрана ни одна модель. Включите модель для запроса.",
                    "text": "", "html": "", "answers": [],
                })

        max_tokens = data.get("max_tokens")
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            max_tokens = None

        compact = data.get("compact")
        if isinstance(compact, dict):
            self.session.set_compact(compact.get("enabled"),
                                      compact.get("keep"),
                                      None)
        strategy = data.get("strategy")
        if isinstance(strategy, dict):
            self.session.set_strategy(strategy.get("strategy"),
                                       strategy.get("window"))
        compact = self.session.get_compact()
        history = self.session.get_context_messages()

        memory = self.session.memory_state()
        mem_items = (len(memory.get("working") or {})
                      + len(memory.get("longterm") or {}))
        if mem_items:
            print("[MEMORY] в запрос добавлена память: рабочая=%d, "
                  "долговременная=%d (всего %d элементов)"
                  % (len(memory.get("working") or {}),
                     len(memory.get("longterm") or {}), mem_items),
                  flush=True)
        else:
            print("[MEMORY] память пуста — в запрос не добавляется", flush=True)

        task_state = self.session.get_task_state()
        if not task_state.get("active"):
            task_state = None

        invariants = self.session.get_invariants()
        if invariants:
            print("[INVARIANT] инвариантов в запросе: %d" % len(invariants),
                  flush=True)

        reminders = mcp_helpers.collect_due_reminders()

        if via_mcp:
            print("[MCP] запрос идёт через MCP (server=%r, model=%r, "
                  "board=%s, composition=%s)"
                  % (srv_state._ServerState.mcp_server or "default",
                     srv_state._ServerState.mcp_model or "auto",
                     target_is_board, composition_active), flush=True)
            if target_is_board:
                print("[MCP] запрос к «Доске»: обновляю данные композицией…",
                      flush=True)
                from ..mcp_orchestrator import composition_run
                try:
                    refresh = composition_run(verbose=False)
                    if not refresh.get("ok"):
                        print("[MCP] обновление «Доски» не удалось: %s"
                              % refresh.get("error"), flush=True)
                except Exception as exc:
                    print("[MCP] обновление «Доски» не удалось: %s" % exc,
                          flush=True)
                result = mcp_helpers.board_direct_result(
                    doska_srv, model=(srv_state._ServerState.mcp_model or None))
                if result.get("ok"):
                    self.session.append_turn(question, {
                        "role": "assistant",
                        "content": result.get("text", ""),
                        "html": result.get("html", ""),
                        "answers": result.get("answers", []),
                        "meta": result.get("meta", ""),
                        "usage": result.get("usage"),
                    })
                    result["compact"] = self.session.get_compact()
                    result["strategy"] = self.session.get_strategy()
                    result["facts"] = self.session.get_facts()
                    result["branches"] = self.session.branches_state()
                    result["memory"] = self.session.memory_state()
                    result["task"] = self.session.get_task_state()
                    result["invariants"] = self.session.invariants_state()
                    result["context"] = self.session.context_stats()
                if reminders:
                    result["reminders"] = reminders
                return self._send_json(200, result)
            tools = []
            if "mcp_client" in dir() or True:
                try:
                    from rtk_app import mcp_client as mc
                    listed = mc.mcp_list_tools(
                        server_id=(srv_state._ServerState.mcp_server or None))
                    if listed.get("ok"):
                        tools = listed.get("tools", [])
                    else:
                        print("[MCP] не удалось получить список инструментов: %s"
                              % listed.get("error"), flush=True)
                except Exception:
                    pass
            result = self.agent.answer_via_mcp(
                question, tools,
                model=(srv_state._ServerState.mcp_model or None),
                server_id=(srv_state._ServerState.mcp_server or None))
        else:
            result = self.agent.answer(question, history, selected,
                                        max_tokens=max_tokens,
                                        compact=compact,
                                        memory=memory,
                                        profile=profile,
                                        answer_title=answer_title,
                                        task_state=task_state,
                                        invariants=invariants)
        if result.get("ok"):
            self.session.append_turn(question, {
                "role": "assistant",
                "content": result.get("text", ""),
                "html": result.get("html", ""),
                "answers": result.get("answers", []),
                "meta": result.get("meta", ""),
                "usage": result.get("usage"),
            })
            self._maybe_update_facts(question, result)
            mused = result.get("memory_used") or {}
            self.session.add_memory_usage(mused.get("working", 0),
                                           mused.get("longterm", 0))
            self._maybe_auto_compact()
            self._maybe_advance_task(question, result)
            result["compact"] = self.session.get_compact()
            result["strategy"] = self.session.get_strategy()
            result["facts"] = self.session.get_facts()
            result["branches"] = self.session.branches_state()
            result["memory"] = self.session.memory_state()
            result["task"] = self.session.get_task_state()
            result["invariants"] = self.session.invariants_state()
            result["context"] = self.session.context_stats()
        if reminders:
            result["reminders"] = reminders
        return self._send_json(200, result)

    def _maybe_advance_task(self, question, result):
        """Продвигает автомат задачи по ходу пользователя (если задача активна)."""
        try:
            ts = self.session.get_task_state()
            if not ts.get("active") or ts.get("paused") or ts.get("stage") == "done":
                return
            move = self.agent.advance_task(
                ts, question, result.get("text", ""))
            if not move or not move.get("stage"):
                return
            res = self.session.advance_task(
                stage=move.get("stage"),
                step=move.get("step"),
                expected=move.get("expected"),
                note=move.get("note") or "авто-переход по ходу диалога")
            if res.get("ok"):
                print("[TASK] этап -> %s (шаг: %s)"
                      % (res["task"].get("stage"), res["task"].get("step")),
                      flush=True)
            else:
                print("[TASK] переход отклонён: %s" % res.get("error"),
                      flush=True)
        except Exception as exc:
            print("[TASK] авто-переход не удался: %s" % exc, flush=True)

    def _maybe_update_facts(self, question, result):
        """Обновляет блок facts после хода пользователя (стратегия Facts)."""
        try:
            if self.session.get_strategy().get("strategy") != "facts":
                return
            prev = self.session.get_facts()
            last_turn = [
                {"role": "user", "content": str(question)},
                {"role": "assistant", "content": result.get("text", "")},
            ]
            facts = self.agent.update_facts(prev, last_turn)
            if isinstance(facts, dict):
                self.session.set_facts(facts)
        except Exception as exc:
            print("[FACTS] обновление не удалось: %s" % exc, flush=True)
