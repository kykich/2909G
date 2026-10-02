"""Вспомогательные обработчики POST-эндпоинтов."""
import urllib.parse

from rtk_app import config


class ApiHandler:
    """Вспомогательные обработчики: compact, strategy, facts, memory и т.д."""

    def _handle_compact(self):
        """Обновляет настройки сжатия сессии (enabled/keep/summary)."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        enabled = data.get("enabled")
        keep = data.get("keep")
        summary = data.get("summary")
        if not summary:
            summary = None
        self.session.set_compact(enabled, keep, summary)
        return self._send_json(200, {
            "ok": True,
            "compact": self.session.get_compact(),
        })

    def _handle_compact_summary(self):
        """Дописывает вытесненную часть истории в summary (по запросу)."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        keep = data.get("keep", config.COMPACT_KEEP)
        try:
            keep = max(0, int(keep))
        except (TypeError, ValueError):
            keep = config.COMPACT_KEEP
        self.session.set_compact(True, keep, None)
        head, end = self.session.head_to_compact()
        if not head:
            return self._send_json(200, {
                "ok": True, "summary": self.session.get_compact().get("summary", ""),
                "detail": "Нет вытесненных сообщений — сжимать нечего.",
            })
        prev_summary = self.session.get_compact().get("summary", "")
        summary = self.agent.compact_update(prev_summary, head)
        if summary:
            self.session.apply_summary(summary, upto=end, keep=keep)
            return self._send_json(200, {
                "ok": True, "summary": summary,
                "detail": "Summary дополнен (%d сообщ.)." % len(head),
            })
        return self._send_json(200, {
            "ok": False, "summary": self.session.get_compact().get("summary", ""),
            "detail": "Не удалось обновить summary.",
        })

    def _handle_strategy(self):
        """Управление стратегией контекста: none / sliding / facts / branch."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        state = self.session.set_strategy(data.get("strategy"),
                                           data.get("window"))
        return self._send_json(200, {
            "ok": True,
            "strategy": state,
            "context": self.session.context_stats(),
            "facts": self.session.get_facts(),
            "branches": self.session.branches_state(),
        })

    def _handle_facts(self):
        """Просмотр/редактирование фактов (key-value) стратегии Facts."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        facts = data.get("facts")
        if isinstance(facts, dict):
            facts = {str(k): str(v) for k, v in facts.items()}
            mem_map = data.get("mem_map")
            if not isinstance(mem_map, dict):
                mem_map = {}
            working, longterm = {}, {}
            for k, v in facts.items():
                layer = str(mem_map.get(k, "working")).strip().lower()
                if layer == "longterm":
                    longterm[k] = v
                else:
                    working[k] = v
            try:
                self.session.set_memory_bulk("working", working)
                self.session.set_memory_bulk("longterm", longterm)
            except ValueError as exc:
                return self._send_json(400, {"ok": False, "error": str(exc)})
        return self._send_json(200, {
            "ok": True,
            "facts": self.session.get_facts(),
            "memory": self.session.memory_state(),
        })

    def _handle_memory(self):
        """Память агента: чтение/запись трёх типов."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        action = str(data.get("action", "state")).strip().lower()
        mem_type = data.get("type")
        try:
            if action == "set":
                entry = self.session.set_memory_key(
                    mem_type, data.get("key"), data.get("value"))
                return self._send_json(200, {
                    "ok": True, "saved": entry,
                    "memory": self.session.memory_state(),
                })
            if action == "delete":
                removed = self.session.delete_memory_key(mem_type,
                                                          data.get("key"))
                return self._send_json(200, {
                    "ok": True, "removed": removed,
                    "memory": self.session.memory_state(),
                })
            if action == "replace":
                saved = self.session.set_memory_bulk(mem_type, data.get("data"))
                return self._send_json(200, {
                    "ok": True, "saved": saved,
                    "memory": self.session.memory_state(),
                })
            if action == "clear":
                mt = str(mem_type or "").strip()
                if mt not in config.MEMORY_TYPES:
                    return self._send_json(400, {
                        "ok": False,
                        "error": "Неизвестный тип памяти: %r" % (mem_type,),
                    })
                if mt == "short":
                    return self._send_json(400, {
                        "ok": False,
                        "error": "Краткосрочная память очищается кнопкой «Новый разговор».",
                    })
                self.session.set_memory_bulk(mt, {})
                return self._send_json(200, {
                    "ok": True, "memory": self.session.memory_state(),
                })
            return self._send_json(200, {
                "ok": True, "memory": self.session.memory_state(),
            })
        except ValueError as exc:
            return self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self._send_json(500, {"ok": False,
                                          "error": "Ошибка памяти: %s" % exc})

    def _handle_branches(self):
        """Управление ветками: create / switch / delete / rename."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        action = str(data.get("action", "")).strip().lower()
        if action == "create":
            state = self.session.create_branch(
                name=data.get("name"),
                count=data.get("count"),
                from_checkpoint=bool(data.get("from_checkpoint", True)))
        elif action == "switch":
            state = self.session.switch_branch(data.get("index"))
        elif action == "delete":
            state = self.session.delete_branch(data.get("index"))
        elif action == "rename":
            state = self.session.rename_branch(data.get("index"),
                                                data.get("name"))
        else:
            return self._send_json(400, {
                "ok": False,
                "error": "Неизвестное действие с ветками (action).",
            })
        return self._send_json(200, {
            "ok": True,
            "branches": state,
            "messages": self.session.snapshot(),
        })

    def _handle_task(self):
        """Управление СОСТОЯНИЕМ ЗАДАЧИ (Task State Machine)."""
        data = self._read_json_body()
        if not data:
            return self._send_json(200, {
                "ok": True, "task": self.session.get_task_state()})
        action = str(data.get("action", "state")).strip().lower()
        try:
            if action == "start":
                task = self.session.start_task(
                    data.get("goal"), step=data.get("step", ""),
                    expected=data.get("expected", ""),
                    stage=data.get("stage", "planning"))
                return self._send_json(200, {"ok": True, "task": task})
            if action == "advance":
                res = self.session.advance_task(
                    stage=data.get("stage"), step=data.get("step"),
                    expected=data.get("expected"), note=data.get("note", ""))
                status = 200 if res.get("ok") else 409
                return self._send_json(status, {
                    "ok": res.get("ok"), "task": res.get("task"),
                    "error": res.get("error")})
            if action == "pause":
                res = self.session.pause_task(data.get("note", ""))
                return self._send_json(200, {"ok": res.get("ok"),
                                              "task": res.get("task")})
            if action == "resume":
                res = self.session.resume_task(data.get("note", ""))
                return self._send_json(200, {"ok": res.get("ok"),
                                              "task": res.get("task")})
            if action == "finish":
                res = self.session.finish_task(data.get("note", ""))
                status = 200 if res.get("ok") else 409
                return self._send_json(status, {
                    "ok": res.get("ok"), "task": res.get("task"),
                    "error": res.get("error")})
            if action == "reset":
                task = self.session.reset_task()
                return self._send_json(200, {"ok": True, "task": task})
            return self._send_json(200, {
                "ok": True, "task": self.session.get_task_state()})
        except ValueError as exc:
            return self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self._send_json(500, {
                "ok": False, "error": "Ошибка состояния задачи: %s" % exc})

    def _handle_profiles(self):
        """Управление ПРОФИЛЯМИ (персонами)."""
        data = self._read_json_body()
        if not data:
            return self._send_json(400, {"ok": False, "error": "Bad JSON."})
        action = str(data.get("action", "list")).strip().lower()
        try:
            if action == "create":
                state = self.session.create_profile(
                    data.get("name"),
                    character=data.get("character"),
                    style=data.get("style"),
                    model=data.get("model"),
                    activate=bool(data.get("activate", True)))
            elif action == "switch":
                state = self.session.switch_profile(data.get("id"))
            elif action == "update":
                state = self.session.update_profile(
                    data.get("id"),
                    name=data.get("name"),
                    character=data.get("character"),
                    style=data.get("style"),
                    model=data.get("model"))
            elif action == "delete":
                state = self.session.delete_profile(data.get("id"))
            elif action in ("list", "state", ""):
                state = self.session.profiles_state()
            else:
                return self._send_json(400, {
                    "ok": False,
                    "error": "Неизвестное действие с профилями (action).",
                })
        except ValueError as exc:
            return self._send_json(400, {"ok": False, "error": str(exc)})
        return self._send_json(200, {
            "ok": True,
            "profiles": state.get("profiles", []),
            "active": state.get("active"),
            "messages": self.session.snapshot(),
            "memory": self.session.memory_state(),
            "branches": self.session.branches_state(),
            "compact": self.session.get_compact(),
            "strategy": self.session.get_strategy(),
            "context": self.session.context_stats(),
        })

    def _handle_invariants(self):
        """Управление ИНВАРИАНТАМИ (правилами, которые нельзя нарушать)."""
        data = self._read_json_body() or {}
        action = str(data.get("action", "state")).strip().lower()
        try:
            if action == "add":
                state = self.session.add_invariant(
                    data.get("text"), data.get("category", "business"))
            elif action == "update":
                state = self.session.update_invariant(
                    data.get("id"), text=data.get("text"),
                    category=data.get("category"))
            elif action == "delete":
                removed = self.session.delete_invariant(data.get("id"))
                state = self.session.invariants_state()
                state["removed"] = removed
            elif action == "replace":
                state = self.session.set_invariants(data.get("invariants"))
            elif action == "clear":
                state = self.session.clear_invariants()
            else:
                state = self.session.invariants_state()
        except ValueError as exc:
            return self._send_json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            return self._send_json(500, {
                "ok": False, "error": "Ошибка инвариантов: %s" % exc})
        return self._send_json(200, state)
