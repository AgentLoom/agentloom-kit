# Roadmap batch

A batch is several linked roadmap tasks added in **one commit** — the shape of
an effort too large for one issue.

1. **Survey the whole effort first.** Decompose by implementation phase,
   architectural layer, capability slice or dependency boundary — never by an
   arbitrary count. Each task is one coherent unit the generator can package.
2. **Wire the structure.** Sibling order goes in `dependencies`; a follow-up or
   subtask names its parent in `parent_id`. Every id you reference must exist in
   the file or be added in the same change; no cycles.
3. **Restructuring an umbrella.** When the new tasks split or narrow an existing
   `planned` task, edit that task in the same commit: narrow its description to
   the residual work and point its `dependencies` at the children. New tasks
   without that edit leave the umbrella eligible with its old scope, and the
   generator builds it twice.
4. **Schedule as one.** Pin all of them when the effort is urgent, park all of
   them when it should wait, otherwise leave `scheduling` absent.
5. **Tag, validate, commit once.**

   ```sh
   python3 $KIT/scripts/roadmap-tag.py task-a task-b task-c
   python3 $KIT/scripts/validate.py roadmap
   git add .seed-engine/roadmap.yml && git commit -m "Plan <effort>"
   git pull --rebase && git push
   ```

   The validator checks every added and edited task jointly: ids unique across
   all versions, every dependency resolvable, no cycle, only `planned` tasks
   edited.

For a very large effort, add the first coherent batch, let the user confirm the
decomposition, then add the next batch against the real ids already committed.

---

*Generated from AgentLoom's authoring rules for engine pin `2026.10.02-stable`.*
