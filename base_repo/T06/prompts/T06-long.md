# T06: Godot Engine — Global Groups Registry

## Requirement — self-contained specification

Upstream reference (do not fetch): `https://github.com/godotengine/godot-proposals/issues/3789` — "Global Groups Editor/Registry". All information required to implement the feature is reproduced below.

---

## 1. Motivation

Godot's scene graph has a built-in "groups" concept: any `Node` can call
`add_to_group("enemies")` at runtime to register itself in a named group, and
`SceneTree.get_nodes_in_group("enemies")` returns them. Groups are widely used
for tagging entities (enemies, pickups, players, triggers) and for addressing
subsets of a scene.

In 3.x, groups exist only implicitly: a group name is created the first time
any node joins it. There is no project-wide index, so typos silently create
new groups, there is no description or documentation attached to any group,
and renaming a group requires touching every scene that references it.

The proposal introduces a **registry of global groups** stored in the project
settings. Registered groups become first-class: they show up in the inspector
with autocomplete, they can carry a description, editor tooling knows which
scenes and nodes belong to which group, and refactors (rename / delete /
merge) can be performed project-wide with confidence.

## 2. Data model

A global group has four pieces of metadata:

| Field | Type | Purpose |
|---|---|---|
| `name` | `StringName` | Unique identifier, matches the string passed to `add_to_group()` |
| `description` | `String` | Free-form description shown in tooltips / docs |
| `scenes` | `Set<String>` | Paths of scene files that reference this group (editor-derived cache) |
| `is_global` | `bool` | Whether the group is promoted to the project registry |

Global groups live in the ProjectSettings section `global_group` and are persisted in `project.godot` under a new `[global_group]` section.

## 3. ProjectSettings API

New entries in `ProjectSettings`:

```
[global_group]
Enemies=""
Friendlies="Characters the player should not attack"
Collectibles=""
```

The value after `=` is the optional description string. Godot's `ProjectSettings` singleton exposes helpers:

```gdscript
ProjectSettings.add_global_group(name: StringName, description: String = "") -> void
ProjectSettings.remove_global_group(name: StringName) -> void
ProjectSettings.has_global_group(name: StringName) -> bool
ProjectSettings.get_global_groups_list() -> PackedStringArray
ProjectSettings.get_global_group_description(name: StringName) -> String
ProjectSettings.set_global_group_description(name: StringName, description: String) -> void
```

Equivalent C++ accessors must be added on the `ProjectSettings` singleton.

## 4. Editor UI

### 4.1 Scene dock — Groups tab enhancements

The existing `GroupsEditor` widget is extended so groups are visually split:

- **Global groups** (bold, with icon) — from ProjectSettings registry.
- **Scene-local groups** — not in the registry; labelled "Local".
- Toggle "Add to scene" button on a global group attaches the node to that group within the scene; turning a scene group into a global one prompts the user and registers it in the project.

Affected editor components: scene-tree dock and the groups editor.

### 4.2 Project Settings → Global Groups tab

Add a new tab inside the Project Settings dialog listing all registered global groups with columns `Name`, `Description`, `Usage count`.

From this panel the user can:

- Add a new global group (name + optional description).
- Rename a group — Godot scans every `.tscn`, `.tres`, and `.gd` file under the project root and rewrites occurrences, showing a confirmation diff.
- Delete a group — with a warning when the group has usages.
- View "where used" listings.

Relevant editor components: project-settings dialog plus a new global-groups editor.

### 4.3 Scene + node linkage

Internally, membership in a group continues to be stored on the `Node` in the scene, as a `PackedStringArray` `groups`. No change to the runtime API. What changes is only the *editor view*.

## 4. File format impact

The `[global_group]` section is serialized at the top of `project.godot` immediately after `[gui]`.

Example:

```
[global_group]
enemies=""
collectibles="Pickups scattered around the level"
```

Scene files (`.tscn`) are unchanged.

## 5. Public API additions

Add these methods to `ProjectSettings`:

```cpp
bool has_global_group(const StringName &p_name) const;
String get_global_group_description(const StringName &p_name) const;
PackedStringArray get_global_group_names() const;
```

Expose them as `ClassDB::bind_method` entries so they are callable from GDScript (`ProjectSettings.has_global_group("enemies")`).

## 6. Runtime / editor behaviour

Runtime behaviour is unchanged: `Node.add_to_group` still accepts any string; using an unregistered name logs an informational message in the editor (not an error at runtime). The editor's script analyser may warn about node scripts that call `add_to_group(...)` with a literal not in the registry.

## 7. Implementation Task

You must:

1. Extend `ProjectSettings` to parse the new `[global_group]` section and provide the CRUD API above.
2. Add the Project Settings tab "Global Groups" with CRUD GUI.
3. Add the Node Inspector Groups panel split.
4. Implement the "rename group across project" path in a new editor group-settings module, including undo/redo support.
5. Add a GDScript unit test under the project-settings test suite that creates a group, renames it, and asserts all descriptions and lookups work.
6. Update the class documentation for `ProjectSettings` and the class-ref for `Node.add_to_group`.

## 8. Acceptance criteria

- Opening an existing project without `[global_group]` works unchanged; the groups tab is empty.
- Adding a global group via the Project Settings UI is persisted to `project.godot`.
- Renaming/deleting a global group propagates to all scenes that reference it.
- Scene files with references to unregistered global groups emit a warning in the editor console.
- Godot's runtime behaviour (`get_groups()`, `add_to_group()`, `SceneTree::get_nodes_in_group()`) is bitwise identical to the prior release.
