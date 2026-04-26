#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync latest UE tracks into a BP_RemoteAudioPlayer actor in current UE level.

Safe default behavior:
- always writes AudioFilePath
- DOES NOT write VisemeKeys unless --apply-viseme is explicitly enabled

This avoids UE crash loops when ScriptStruct array conversion is incompatible.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import unreal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stream-dir",
        default=r"C:\Users\FYF\Documents\GitHub\FuChuangSai_A22\tmp\ue_a2f_runtime\demo_s1\demo_stream_1",
    )
    parser.add_argument("--actor-label", default="BP_RemoteAudioPlayer")
    parser.add_argument("--tracks-file", default="latest_ue_tracks.json")
    parser.add_argument("--apply-viseme", action="store_true")
    parser.add_argument("--apply-viseme-inplace", action="store_true")
    parser.add_argument("--dump-viseme-schema", action="store_true")
    parser.add_argument("--save-level", action="store_true")
    parser.add_argument(
        "--disable-media-restart",
        action="store_true",
        help="Only update AudioFilePath/SrcRef, do not close/open/play MediaPlayer each turn.",
    )
    parser.add_argument(
        "--enable-ke-fallback",
        action="store_true",
        help="Try `ke <ActorName> <Function>` fallback when direct function calls fail.",
    )
    parser.add_argument(
        "--allow-editor-world",
        action="store_true",
        help="Allow writing actor properties in editor_world when runtime world is unavailable.",
    )
    known, _ = parser.parse_known_args(sys.argv[1:])
    return known


def _log(msg: str) -> None:
    unreal.log("[ue_sync_latest_to_actor] " + msg)


def _warn(msg: str) -> None:
    unreal.log_warning("[ue_sync_latest_to_actor] " + msg)


def _err(msg: str) -> None:
    unreal.log_error("[ue_sync_latest_to_actor] " + msg)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_file_uri(path_text: str) -> str:
    path = Path(path_text).expanduser().resolve()
    return "file:///" + str(path).replace("\\", "/")


def _safe_actor_label(actor) -> str:
    try:
        label = actor.get_actor_label()
        if isinstance(label, str) and label:
            return label
    except Exception:
        pass
    try:
        name = actor.get_name()
        if isinstance(name, str):
            return name
    except Exception:
        pass
    return ""


def _iter_world_actors(world) -> list[Any]:
    if world is None:
        return []
    try:
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
    except Exception:
        return []


def _iter_world_candidates() -> list[tuple[str, Any]]:
    worlds: list[tuple[str, Any]] = []
    # Prefer the newer UnrealEditorSubsystem APIs; keep deprecated fallback.
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    except Exception:
        ues = None

    # Runtime world first (PIE / standalone game world).
    # IMPORTANT: in PIE there can be same-label actors in editor world and PIE world;
    # always prioritize PIE worlds to avoid writing to editor actor by mistake.
    if ues is not None:
        # Some UE versions require include_dedicated_server=True to return active PIE worlds.
        for include_ds in (False, True):
            try:
                pie_worlds = ues.get_pie_worlds(include_ds)
                for idx, pie_world in enumerate(pie_worlds):
                    if pie_world is not None:
                        worlds.append((f"pie_world_{idx}_ds{int(include_ds)}", pie_world))
            except Exception:
                pass
        try:
            game_world = ues.get_game_world()
            if game_world is not None:
                worlds.append(("game_world", game_world))
        except Exception:
            pass
        try:
            editor_world = ues.get_editor_world()
            if editor_world is not None:
                worlds.append(("editor_world", editor_world))
        except Exception:
            pass

    if not worlds:
        try:
            pie_worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
            for idx, pie_world in enumerate(pie_worlds):
                if pie_world is not None:
                    worlds.append((f"pie_world_{idx}", pie_world))
        except Exception:
            pass
        try:
            game_world = unreal.EditorLevelLibrary.get_game_world()
            if game_world is not None:
                worlds.append(("game_world", game_world))
        except Exception:
            pass
        try:
            editor_world = unreal.EditorLevelLibrary.get_editor_world()
            if editor_world is not None:
                worlds.append(("editor_world", editor_world))
        except Exception:
            pass

    # De-duplicate identical world pointers while preserving order.
    seen_ids: set[int] = set()
    unique_worlds: list[tuple[str, Any]] = []
    for scope, world in worlds:
        wid = id(world)
        if wid in seen_ids:
            continue
        seen_ids.add(wid)
        unique_worlds.append((scope, world))
    return unique_worlds


def _find_actor_by_label(actor_label: str, allow_editor_world: bool = False):
    key = (actor_label or "").strip().lower()
    if not key:
        return None

    worlds = _iter_world_candidates()
    runtime_worlds: list[tuple[str, Any]] = []
    editor_worlds: list[tuple[str, Any]] = []
    for scope, world in worlds:
        if scope.startswith("editor_world"):
            editor_worlds.append((scope, world))
        else:
            runtime_worlds.append((scope, world))

    # Pass 1: runtime worlds only.
    for scope, world in runtime_worlds:
        actors = _iter_world_actors(world)
        try:
            world_name = world.get_name()
        except Exception:
            world_name = "unknown_world"
        _log(f"scan {scope} world={world_name} actor_count={len(actors)}")
        for actor in actors:
            label = _safe_actor_label(actor)
            if label.lower() == key:
                _log(f"actor matched exact in {scope}: {label}")
                return actor
        for actor in actors:
            label = _safe_actor_label(actor)
            if label.lower().startswith(key):
                _log(f"actor matched prefix in {scope}: {label}")
                return actor

    if runtime_worlds and not allow_editor_world:
        _warn("no actor matched in runtime worlds; skip editor_world by default")
        return None

    # Pass 2: editor world fallback (explicit opt-in or no runtime worlds available).
    if not allow_editor_world and editor_worlds:
        _warn("runtime world not found; skip editor_world (use --allow-editor-world to override)")
        return None

    for scope, world in editor_worlds:
        actors = _iter_world_actors(world)
        try:
            world_name = world.get_name()
        except Exception:
            world_name = "unknown_world"
        _log(f"scan {scope} world={world_name} actor_count={len(actors)}")
        for actor in actors:
            label = _safe_actor_label(actor)
            if label.lower() == key:
                _log(f"actor matched exact in {scope}: {label}")
                return actor
        for actor in actors:
            label = _safe_actor_label(actor)
            if label.lower().startswith(key):
                _log(f"actor matched prefix in {scope}: {label}")
                return actor

    # Fallback: editor actor subsystem.
    if allow_editor_world:
        try:
            actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
            actors = actor_subsystem.get_all_level_actors()
        except Exception:
            actors = []
        for actor in actors:
            label = _safe_actor_label(actor)
            if label.lower() == key:
                _log(f"actor matched exact in editor_subsystem: {label}")
                return actor
        for actor in actors:
            label = _safe_actor_label(actor)
            if label.lower().startswith(key):
                _log(f"actor matched prefix in editor_subsystem: {label}")
                return actor
    return None


def _get_cdo(obj):
    try:
        cls = obj.get_class()
        return unreal.get_default_object(cls)
    except Exception:
        return None


def _try_get_prop(obj, name: str):
    try:
        return True, obj.get_editor_property(name), ""
    except Exception as exc1:
        try:
            return True, getattr(obj, name), ""
        except Exception as exc2:
            return (
                False,
                None,
                f"editor_property={type(exc1).__name__}: {exc1}; "
                f"getattr={type(exc2).__name__}: {exc2}",
            )


def _try_set_prop(obj, name: str, value):
    try:
        obj.set_editor_property(name, value)
        return True, ""
    except Exception as exc1:
        try:
            setattr(obj, name, value)
            return True, ""
        except Exception as exc2:
            return (
                False,
                f"editor_property={type(exc1).__name__}: {exc1}; "
                f"setattr={type(exc2).__name__}: {exc2}",
            )


def _resolve_prop(actor, names: list[str]):
    errors: list[str] = []
    cdo = _get_cdo(actor)
    for scope, obj in (("actor", actor), ("cdo", cdo)):
        if obj is None:
            continue
        for name in names:
            ok, value, err = _try_get_prop(obj, name)
            if ok:
                return scope, obj, name, value, ""
            errors.append(f"{scope}.{name}: {err}")
    return "", None, "", None, " | ".join(errors)


def _set_prop_with_fallback(actor, names: list[str], value):
    errors: list[str] = []
    cdo = _get_cdo(actor)
    for scope, obj in (("actor", actor), ("cdo", cdo)):
        if obj is None:
            continue
        for name in names:
            ok, err = _try_set_prop(obj, name, value)
            if ok:
                return scope, name, ""
            errors.append(f"{scope}.{name}: {err}")
    return "", "", " | ".join(errors)


def _list_struct_fields(struct_value) -> list[str]:
    names: list[str] = []
    for name in dir(struct_value):
        if name.startswith("_"):
            continue
        try:
            attr = getattr(struct_value, name)
        except Exception:
            continue
        if callable(attr):
            continue
        names.append(name)
    return names


def _pick_field_name(field_names: list[str], aliases: list[str], contains_any: list[str]) -> str:
    lower_map = {name.lower(): name for name in field_names}
    for alias in aliases:
        found = lower_map.get(alias.lower())
        if found:
            return found
    for name in field_names:
        lower = name.lower()
        for token in contains_any:
            if token in lower:
                return name
    return ""


def _set_struct_field(struct_obj, field_name: str, value) -> bool:
    if not field_name:
        return False
    try:
        struct_obj.set_editor_property(field_name, value)
        return True
    except Exception:
        pass
    try:
        setattr(struct_obj, field_name, value)
        return True
    except Exception:
        return False


def _set_struct_field_any(struct_obj, field_names: list[str], value) -> str:
    for name in field_names:
        if _set_struct_field(struct_obj, name, value):
            return name
    return ""


def _set_curve_field(struct_obj, field_name: str, curve_text: str) -> bool:
    if not field_name:
        return False
    if _set_struct_field(struct_obj, field_name, unreal.Name(curve_text)):
        return True
    return _set_struct_field(struct_obj, field_name, curve_text)


def _set_curve_field_any(struct_obj, field_names: list[str], curve_text: str) -> str:
    for name in field_names:
        if not name:
            continue
        if _set_curve_field(struct_obj, name, curve_text):
            return name
    return ""


def _compress_viseme_curves(viseme_curves: list[dict[str, Any]], max_units: int) -> list[dict[str, Any]]:
    if max_units <= 0:
        return []
    if len(viseme_curves) <= max_units:
        return viseme_curves
    out: list[dict[str, Any]] = []
    last_idx = -1
    for i in range(max_units):
        idx = round(i * (len(viseme_curves) - 1) / (max_units - 1))
        if idx == last_idx:
            continue
        item = viseme_curves[idx]
        if isinstance(item, dict):
            out.append(item)
            last_idx = idx
    return out


def _build_viseme_dict_payload(viseme_curves: list[dict[str, Any]], current_prop_value):
    """
    Build list[dict] payload only (no struct instantiation) to reduce crash risk.
    """
    template_fields: list[str] = []
    try:
        if len(current_prop_value) > 0:
            template_fields = _list_struct_fields(current_prop_value[0])
    except Exception:
        template_fields = []

    field_map = {
        "start": _pick_field_name(
            template_fields,
            aliases=["StartMs", "start_ms", "startms", "StartTimeMs", "start_time_ms"],
            contains_any=["start", "begin"],
        ),
        "end": _pick_field_name(
            template_fields,
            aliases=["EndMs", "end_ms", "endms", "EndTimeMs", "end_time_ms"],
            contains_any=["end", "stop"],
        ),
        "curve": _pick_field_name(
            template_fields,
            aliases=["Curve", "curve", "CurveName", "curve_name", "Viseme", "viseme", "Name", "name"],
            contains_any=["curve", "viseme", "phoneme", "name"],
        ),
        "weight": _pick_field_name(
            template_fields,
            aliases=["Weight", "weight", "Value", "value", "Alpha", "alpha", "Intensity", "intensity"],
            contains_any=["weight", "value", "alpha", "intensity"],
        ),
    }

    # fallback names (common convention)
    if not field_map["start"]:
        field_map["start"] = "StartMs"
    if not field_map["end"]:
        field_map["end"] = "EndMs"
    if not field_map["curve"]:
        field_map["curve"] = "Curve"
    if not field_map["weight"]:
        field_map["weight"] = "Weight"

    payload: list[dict[str, Any]] = []
    for item in viseme_curves:
        if not isinstance(item, dict):
            continue
        payload.append(
            {
                field_map["start"]: _safe_int(item.get("start_ms"), 0),
                field_map["end"]: _safe_int(item.get("end_ms"), 0),
                field_map["curve"]: str(item.get("curve", "Mouth_Closed")),
                field_map["weight"]: _safe_float(item.get("weight"), 0.0),
            }
        )
    return payload, field_map, template_fields


def _build_viseme_primitive_arrays(viseme_curves: list[dict[str, Any]]):
    starts: list[int] = []
    ends: list[int] = []
    curves: list[str] = []
    weights: list[float] = []
    for item in viseme_curves:
        if not isinstance(item, dict):
            continue
        starts.append(_safe_int(item.get("start_ms"), 0))
        ends.append(_safe_int(item.get("end_ms"), 0))
        curves.append(str(item.get("curve", "Mouth_Closed")))
        weights.append(_safe_float(item.get("weight"), 0.0))
    return starts, ends, curves, weights


def _set_prop_with_fallback_multi(actor, name_groups: list[list[str]], value):
    errors: list[str] = []
    for names in name_groups:
        scope, prop_name, err = _set_prop_with_fallback(actor, names, value)
        if prop_name:
            return scope, prop_name, ""
        if err:
            errors.append(err)
    return "", "", " | ".join(errors)


def _set_curve_array_with_fallback(actor, name_groups: list[list[str]], curves: list[str]):
    name_values = [unreal.Name(c) for c in curves]
    scope, prop_name, err = _set_prop_with_fallback_multi(actor, name_groups, name_values)
    if prop_name:
        return scope, prop_name, "name[]"

    scope2, prop_name2, err2 = _set_prop_with_fallback_multi(actor, name_groups, curves)
    if prop_name2:
        return scope2, prop_name2, "string[]"

    merged = " | ".join(part for part in [err, err2] if part)
    return "", "", merged


def _get_array_len(actor, names: list[str]) -> int:
    scope, obj, prop_name, value, _ = _resolve_prop(actor, names)
    if not prop_name:
        return -1
    try:
        return len(value)
    except Exception:
        return -1


def _get_viseme_len(actor) -> int:
    return _get_array_len(actor, ["VisemeKeys", "viseme_keys"])


def _get_pending_len(actor) -> int:
    length = _get_array_len(actor, ["PendingVisemeStartMs", "pending_viseme_start_ms"])
    if length >= 0:
        return length
    return _get_array_len(actor, ["VisemeStartMs", "viseme_start_ms"])


def _try_call_build_viseme(actor, enable_ke_fallback: bool = False) -> tuple[bool, str]:
    def _find_candidate_callables() -> list[str]:
        out: list[str] = []
        tokens = ["viseme", "pending", "build", "mouth", "phoneme"]
        try:
            for name in dir(actor):
                lname = name.lower()
                if not any(t in lname for t in tokens):
                    continue
                try:
                    attr = getattr(actor, name)
                except Exception:
                    continue
                if callable(attr):
                    out.append(name)
        except Exception:
            return []
        return sorted(set(out))

    errors: list[str] = []
    before_pending = _get_pending_len(actor)
    before_viseme = _get_viseme_len(actor)

    def _state_changed() -> tuple[bool, str]:
        after_pending = _get_pending_len(actor)
        after_viseme = _get_viseme_len(actor)
        changed = (after_pending != before_pending) or (after_viseme != before_viseme)
        info = (
            f"pending:{before_pending}->{after_pending}, "
            + f"viseme:{before_viseme}->{after_viseme}"
        )
        return changed, info

    candidates = _find_candidate_callables()
    if candidates:
        _log("viseme callable candidates: " + ", ".join(candidates[:30]))

    for method_name in [
        "build_viseme_keys_from_pending",
        "BuildVisemeKeysFromPending",
        "ApplyPendingVisemeNow",
        "ApplyPendingVisemes",
        "RefreshVisemeFromPending",
    ]:
        try:
            method = getattr(actor, method_name)
            if callable(method):
                method()
                changed, state_info = _state_changed()
                if changed:
                    return True, method_name + "() " + state_info
                errors.append(method_name + "() invoked but no state change: " + state_info)
        except Exception as exc:
            errors.append(f"{method_name}: {type(exc).__name__}: {exc}")

    # Fallback 1: UObject call by function name (works on some UE Python bindings).
    try:
        actor.call_function_by_name_with_arguments("BuildVisemeKeysFromPending", None, None, True)
        changed, state_info = _state_changed()
        if changed:
            return True, "call_function_by_name_with_arguments(BuildVisemeKeysFromPending) " + state_info
        errors.append(
            "call_function_by_name_with_arguments(BuildVisemeKeysFromPending) invoked but no state change: "
            + state_info
        )
    except Exception as exc:
        errors.append(f"call_function_by_name_with_arguments: {type(exc).__name__}: {exc}")

    for fn_name in [
        "build_viseme_keys_from_pending",
        "ApplyPendingVisemeNow",
        "ApplyPendingVisemes",
        "RefreshVisemeFromPending",
    ]:
        try:
            actor.call_function_by_name_with_arguments(fn_name, None, None, True)
            changed, state_info = _state_changed()
            if changed:
                return True, f"call_function_by_name_with_arguments({fn_name}) {state_info}"
            errors.append(
                f"call_function_by_name_with_arguments({fn_name}) invoked but no state change: {state_info}"
            )
        except Exception as exc:
            errors.append(f"call_function_by_name_with_arguments[{fn_name}]: {type(exc).__name__}: {exc}")

    def _actor_console_targets() -> list[str]:
        refs: list[str] = []
        try:
            path_name = str(actor.get_path_name())
            if path_name:
                refs.append(path_name)
        except Exception:
            pass
        try:
            obj_name = str(actor.get_name())
            if obj_name:
                refs.append(obj_name)
        except Exception:
            pass
        label = _safe_actor_label(actor)
        if label:
            refs.append(label)
        # deduplicate while preserving order
        out: list[str] = []
        seen: set[str] = set()
        for ref in refs:
            if ref in seen:
                continue
            seen.add(ref)
            out.append(ref)
        return out

    # Optional fallback: Kismet console event call (ke <ActorRef> <FunctionOrEvent>).
    if enable_ke_fallback:
        runtime_world = _try_get_runtime_world()
        if runtime_world is not None:
            actor_refs = _actor_console_targets()
            if actor_refs:
                for fn_name in [
                    "BuildVisemeKeysFromPending",
                    "build_viseme_keys_from_pending",
                    "ApplyPendingVisemeNow",
                    "ApplyPendingVisemes",
                    "RefreshVisemeFromPending",
                ]:
                    for actor_ref in actor_refs:
                        # Quote actor ref to keep full PIE object path intact.
                        cmd = f'ke "{actor_ref}" {fn_name}'
                        try:
                            unreal.SystemLibrary.execute_console_command(runtime_world, cmd)
                            changed, state_info = _state_changed()
                            if changed:
                                return True, f"execute_console_command({cmd}) {state_info}"
                            errors.append(
                                f"console_command[{cmd}] invoked but no state change: {state_info}"
                            )
                        except Exception as exc:
                            errors.append(f"console_command[{cmd}]: {type(exc).__name__}: {exc}")

    return False, " | ".join(errors)


def _sync_src_ref_file_path(actor, local_audio_path: str) -> tuple[bool, str]:
    """
    If BP still uses OpenSource(SrcRef), keep SrcRef's file path in sync.
    """
    scope, target_obj, prop_name, src_ref_obj, resolve_err = _resolve_prop(actor, ["SrcRef", "src_ref"])
    if not prop_name:
        return False, f"SrcRef not found: {resolve_err}"
    if src_ref_obj is None:
        return False, f"{prop_name}({scope}) is None"

    # FileMediaSource usually exposes set_file_path(str).
    try:
        src_ref_obj.set_file_path(local_audio_path)
        return True, f"set {prop_name}({scope}).set_file_path({local_audio_path})"
    except Exception as exc:
        err1 = f"{type(exc).__name__}: {exc}"

    # Fallback attempts for engines/plugins with different bindings.
    try:
        src_ref_obj.set_editor_property("file_path", local_audio_path)
        return True, f"set {prop_name}({scope}).file_path={local_audio_path}"
    except Exception as exc:
        err2 = f"{type(exc).__name__}: {exc}"

    # Some bindings expose FilePath struct wrapper.
    try:
        fp = unreal.FilePath()
        fp.file_path = local_audio_path
        src_ref_obj.set_editor_property("file_path", fp)
        return True, f"set {prop_name}({scope}).file_path(FilePath)={local_audio_path}"
    except Exception as exc:
        err3 = f"{type(exc).__name__}: {exc}"

    return False, f"src_ref path sync failed: method:{err1} | raw_prop:{err2} | filepath_struct:{err3}"


def _try_get_runtime_world():
    try:
        ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    except Exception:
        ues = None
    if ues is not None:
        for include_ds in (False, True):
            try:
                pie_worlds = ues.get_pie_worlds(include_ds)
                if pie_worlds:
                    return pie_worlds[0]
            except Exception:
                pass
        try:
            world = ues.get_game_world()
            if world is not None:
                return world
        except Exception:
            pass
    try:
        pie_worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
        if pie_worlds:
            return pie_worlds[0]
    except Exception:
        pass
    try:
        return unreal.EditorLevelLibrary.get_game_world()
    except Exception:
        return None


def _try_restart_media_playback(actor) -> tuple[bool, str]:
    mp_scope, mp_target, mp_name, mp_obj, mp_err = _resolve_prop(actor, ["MPRef", "mp_ref"])
    if not mp_name or mp_obj is None:
        return False, f"MPRef not found: {mp_err}"

    src_scope, src_target, src_name, src_obj, src_err = _resolve_prop(actor, ["SrcRef", "src_ref"])
    if not src_name or src_obj is None:
        return False, f"SrcRef not found: {src_err}"

    notes: list[str] = []
    try:
        mp_obj.close()
        notes.append("close()")
    except Exception:
        pass

    try:
        opened = bool(mp_obj.open_source(src_obj))
        notes.append(f"open_source({src_name})={opened}")
    except Exception as exc:
        return False, f"open_source failed: {type(exc).__name__}: {exc}"
    if not opened:
        return False, "open_source returned False"

    try:
        played = bool(mp_obj.play())
        notes.append(f"play()={played}")
    except Exception as exc:
        return False, f"play failed: {type(exc).__name__}: {exc}"

    runtime_world = _try_get_runtime_world()
    now_sec = 0.0
    if runtime_world is not None:
        try:
            now_sec = float(unreal.GameplayStatics.get_time_seconds(runtime_world))
        except Exception:
            now_sec = 0.0
    as_ok1, as_err1 = _try_set_prop(actor, "AudioStartSec", now_sec)
    if as_ok1:
        notes.append(f"set AudioStartSec(actor)={now_sec:.3f}")
    else:
        as_ok2, as_err2 = _try_set_prop(actor, "audio_start_sec", now_sec)
        if as_ok2:
            notes.append(f"set audio_start_sec(actor)={now_sec:.3f}")
        else:
            as_scope, as_name, as_err = _set_prop_with_fallback(
                actor, ["AudioStartSec", "audio_start_sec"], now_sec
            )
            if as_name:
                notes.append(f"set {as_name}({as_scope})={now_sec:.3f}")
            else:
                notes.append(
                    "set AudioStartSec failed: "
                    + " | ".join(part for part in [as_err1, as_err2, as_err] if part)
                )

    return True, " ; ".join(notes)


def _ensure_face_mesh_ref(actor) -> tuple[bool, str]:
    fa_scope, fa_target, fa_name, face_actor, fa_err = _resolve_prop(
        actor, ["FaceActorRef", "face_actor_ref"]
    )
    if not fa_name or face_actor is None:
        return False, f"FaceActorRef missing: {fa_err}"

    try:
        sk_comp = face_actor.get_component_by_class(unreal.SkeletalMeshComponent)
    except Exception as exc:
        return False, f"get_component_by_class failed: {type(exc).__name__}: {exc}"
    if sk_comp is None:
        return False, "FaceActorRef has no SkeletalMeshComponent"

    fm_scope, fm_name, fm_err = _set_prop_with_fallback(actor, ["FaceMeshRef", "face_mesh_ref"], sk_comp)
    if fm_name:
        return True, f"set {fm_name}({fm_scope}) from {fa_name}({fa_scope})"
    return False, f"set FaceMeshRef failed: {fm_err}"


def _set_viseme_aux_arrays(actor, viseme_curves: list[dict[str, Any]]):
    """
    Fallback path when ST_VisemeKey is not writable from Python:
    push primitive arrays to BP vars and let BP convert to ST_VisemeKey[].
    """
    starts, ends, curves, weights = _build_viseme_primitive_arrays(viseme_curves)
    if not starts:
        return False, "no viseme curves to push"

    start_groups = [
        ["PendingVisemeStartMs", "pending_viseme_start_ms"],
        ["VisemeStartMs", "viseme_start_ms"],
    ]
    end_groups = [
        ["PendingVisemeEndMs", "pending_viseme_end_ms"],
        ["VisemeEndMs", "viseme_end_ms"],
    ]
    curve_groups = [
        ["PendingVisemeCurves", "pending_viseme_curves"],
        ["VisemeCurves", "viseme_curves"],
        ["PendingVisemeCurveNames", "pending_viseme_curve_names"],
        ["VisemeCurveNames", "viseme_curve_names"],
    ]
    weight_groups = [
        ["PendingVisemeWeights", "pending_viseme_weights"],
        ["VisemeWeights", "viseme_weights"],
    ]

    s_scope, s_name, s_err = _set_prop_with_fallback_multi(actor, start_groups, starts)
    e_scope, e_name, e_err = _set_prop_with_fallback_multi(actor, end_groups, ends)
    c_scope, c_name, c_mode_or_err = _set_curve_array_with_fallback(actor, curve_groups, curves)
    w_scope, w_name, w_err = _set_prop_with_fallback_multi(actor, weight_groups, weights)

    if s_name and e_name and c_name and w_name:
        return True, (
            "aux arrays set "
            + f"count={len(starts)} "
            + f"start={s_name}({s_scope}) "
            + f"end={e_name}({e_scope}) "
            + f"curve={c_name}({c_scope},{c_mode_or_err}) "
            + f"weight={w_name}({w_scope})"
        )

    problems = []
    if not s_name:
        problems.append(f"start_fail:{s_err}")
    if not e_name:
        problems.append(f"end_fail:{e_err}")
    if not c_name:
        problems.append(f"curve_fail:{c_mode_or_err}")
    if not w_name:
        problems.append(f"weight_fail:{w_err}")
    return False, " | ".join(problems)


def _apply_viseme_inplace(current_prop_value, viseme_curves: list[dict[str, Any]]):
    """
    Lower-risk mode:
    - do NOT create new struct types
    - only mutate existing array items in place
    """
    try:
        current_count = len(current_prop_value)
    except Exception as exc:
        return False, f"cannot read current VisemeKeys count: {type(exc).__name__}: {exc}"

    if current_count <= 0:
        return False, "current VisemeKeys array is empty; cannot infer struct type for in-place update"

    try:
        first_item = current_prop_value[0]
        template_fields = _list_struct_fields(first_item)
    except Exception as exc:
        return False, f"cannot inspect VisemeKeys[0] fields: {type(exc).__name__}: {exc}"

    start_candidates = [
        _pick_field_name(
            template_fields,
            aliases=["StartMs", "start_ms", "startms", "StartTimeMs", "start_time_ms"],
            contains_any=["start", "begin"],
        ),
        "StartMs",
        "start_ms",
        "startms",
        "StartTimeMs",
        "start_time_ms",
        "StartTime",
        "start_time",
    ]
    end_candidates = [
        _pick_field_name(
            template_fields,
            aliases=["EndMs", "end_ms", "endms", "EndTimeMs", "end_time_ms"],
            contains_any=["end", "stop"],
        ),
        "EndMs",
        "end_ms",
        "endms",
        "EndTimeMs",
        "end_time_ms",
        "EndTime",
        "end_time",
    ]
    curve_candidates = [
        _pick_field_name(
            template_fields,
            aliases=["Curve", "curve", "CurveName", "curve_name", "Viseme", "viseme", "Name", "name"],
            contains_any=["curve", "viseme", "phoneme", "name"],
        ),
        "Curve",
        "curve",
        "CurveName",
        "curve_name",
        "Viseme",
        "viseme",
        "Name",
        "name",
    ]
    weight_candidates = [
        _pick_field_name(
            template_fields,
            aliases=["Weight", "weight", "Value", "value", "Alpha", "alpha", "Intensity", "intensity"],
            contains_any=["weight", "value", "alpha", "intensity"],
        ),
        "Weight",
        "weight",
        "Value",
        "value",
        "Alpha",
        "alpha",
        "Intensity",
        "intensity",
    ]

    resolved = {
        "start": "",
        "end": "",
        "curve": "",
        "weight": "",
    }
    success = {
        "start": 0,
        "end": 0,
        "curve": 0,
        "weight": 0,
    }

    compressed = _compress_viseme_curves(viseme_curves, current_count)
    source_count = len(compressed)
    if source_count <= 0:
        compressed = [
            {"start_ms": 0, "end_ms": 1, "curve": "Mouth_Closed", "weight": 0.0},
        ]
        source_count = 1

    # Fill each existing struct slot.
    last_end = 0
    for idx in range(current_count):
        src = compressed[idx] if idx < source_count else compressed[-1]
        item = current_prop_value[idx]
        start_ms = _safe_int(src.get("start_ms"), last_end)
        end_ms = _safe_int(src.get("end_ms"), start_ms)
        if end_ms < start_ms:
            end_ms = start_ms
        curve_text = str(src.get("curve", "Mouth_Closed"))
        weight = _safe_float(src.get("weight"), 0.0)

        start_name = _set_struct_field_any(item, start_candidates, start_ms)
        end_name = _set_struct_field_any(item, end_candidates, end_ms)
        curve_name = _set_curve_field_any(item, curve_candidates, curve_text)
        weight_name = _set_struct_field_any(item, weight_candidates, weight)

        if start_name:
            success["start"] += 1
            if not resolved["start"]:
                resolved["start"] = start_name
        if end_name:
            success["end"] += 1
            if not resolved["end"]:
                resolved["end"] = end_name
        if curve_name:
            success["curve"] += 1
            if not resolved["curve"]:
                resolved["curve"] = curve_name
        if weight_name:
            success["weight"] += 1
            if not resolved["weight"]:
                resolved["weight"] = weight_name
        last_end = end_ms

    if success["start"] == 0 and success["end"] == 0 and success["curve"] == 0 and success["weight"] == 0:
        return False, (
            "all viseme field writes failed (no struct member matched known aliases); "
            + f"first_item_type={type(first_item).__name__}; "
            + f"first_item_repr={first_item!r}"
        )

    return True, (
        "inplace_ok "
        + f"slots={current_count} source={len(viseme_curves)} compressed={source_count} "
        + "map="
        + f"start:{resolved['start']},end:{resolved['end']},curve:{resolved['curve']},weight:{resolved['weight']} "
        + "writes="
        + f"start:{success['start']},end:{success['end']},curve:{success['curve']},weight:{success['weight']}"
    )


def main() -> int:
    args = parse_args()
    stream_dir = Path(args.stream_dir).expanduser()
    tracks_path = stream_dir / args.tracks_file
    if not tracks_path.exists():
        _err(f"tracks file not found: {tracks_path}")
        return 1

    try:
        tracks = json.loads(tracks_path.read_text(encoding="utf-8"))
    except Exception as exc:
        _err(f"failed to parse json: {type(exc).__name__}: {exc}")
        return 1

    actor = _find_actor_by_label(args.actor_label, allow_editor_world=args.allow_editor_world)
    if actor is None:
        _err(f"actor not found in runtime world by label: {args.actor_label}")
        return 1

    # 1) always update audio path
    audio_path = tracks.get("audio_path")
    if isinstance(audio_path, str) and audio_path.strip():
        audio_local_path = str(Path(audio_path.strip()).expanduser().resolve())
        audio_uri = _normalize_file_uri(audio_local_path)
        audio_scope, audio_name, audio_err = _set_prop_with_fallback(
            actor, ["AudioFilePath", "audio_file_path"], audio_uri
        )
        if audio_name:
            _log(f"set {audio_name} ({audio_scope}) = {audio_uri}")
        else:
            _warn(f"failed to set AudioFilePath/audio_file_path: {audio_err}")

        # Keep optional SrcRef(MediaSource) in sync for OpenSource pipelines.
        src_ok, src_info = _sync_src_ref_file_path(actor, audio_local_path)
        if src_ok:
            _log(src_info)
        else:
            _warn(src_info)

        face_ok, face_info = _ensure_face_mesh_ref(actor)
        if face_ok:
            _log(face_info)
        else:
            _warn(face_info)

        if args.disable_media_restart:
            _log("media restart skipped (--disable-media-restart)")
        else:
            play_ok, play_info = _try_restart_media_playback(actor)
            if play_ok:
                _log("media restart: " + play_info)
            else:
                _warn("media restart failed: " + play_info)
    else:
        _warn("audio_path missing in latest_ue_tracks.json")

    # 2) viseme schema diagnostics (no write)
    vis_scope, vis_target, vis_name, current_viseme_prop, vis_err = _resolve_prop(
        actor, ["VisemeKeys", "viseme_keys"]
    )
    if not vis_name:
        _warn(f"VisemeKeys not resolved: {vis_err}")
    else:
        _log(f"resolved {vis_name} on {vis_scope}")
        try:
            current_count = len(current_viseme_prop)
        except Exception:
            current_count = -1
        _log(f"current {vis_name} count={current_count}")
        if current_count > 0:
            try:
                first_item = current_viseme_prop[0]
                _log(
                    "viseme first item: "
                    + f"type={type(first_item).__name__} repr={first_item!r}"
                )
            except Exception as exc:
                _warn(f"failed to inspect viseme first item: {type(exc).__name__}: {exc}")
        if args.dump_viseme_schema:
            try:
                if current_count > 0:
                    fields = _list_struct_fields(current_viseme_prop[0])
                    if fields:
                        _log("viseme struct fields: " + ", ".join(fields))
                    else:
                        _warn("viseme struct fields empty in python reflection")
                else:
                    _warn("viseme struct fields unavailable because current array is empty")
            except Exception as exc:
                _warn(f"failed to inspect viseme fields: {type(exc).__name__}: {exc}")

    # 3) optional viseme apply (opt-in only)
    viseme_curves = tracks.get("viseme_curves") or []
    if not isinstance(viseme_curves, list):
        viseme_curves = []

    if args.apply_viseme_inplace:
        if not vis_name:
            _warn("skip viseme apply-inplace because VisemeKeys not resolved")
        else:
            ok, info = _apply_viseme_inplace(current_viseme_prop, viseme_curves)
            if not ok:
                _warn(f"failed to apply viseme inplace: {info}")
                vis_payload, field_map, template_fields = _build_viseme_dict_payload(
                    viseme_curves, current_viseme_prop
                )
                _log(
                    "fallback dict map="
                    + f"start:{field_map['start']},end:{field_map['end']},"
                    + f"curve:{field_map['curve']},weight:{field_map['weight']}"
                )
                if template_fields:
                    _log("fallback template fields=" + ", ".join(template_fields))
                dict_ok, dict_err = _try_set_prop(vis_target, vis_name, vis_payload)
                if dict_ok:
                    _log(f"fallback dict set {vis_name} ({vis_scope}) count={len(vis_payload)}")
                else:
                    _warn(f"fallback dict set failed: {dict_err}")
                    aux_ok, aux_info = _set_viseme_aux_arrays(actor, viseme_curves)
                    if aux_ok:
                        _log("fallback aux viseme arrays applied")
                        _log(aux_info)
                        call_ok, call_info = _try_call_build_viseme(
                            actor, enable_ke_fallback=args.enable_ke_fallback
                        )
                        if call_ok:
                            _log(f"called {call_info}")
                        else:
                            _warn(
                                "aux arrays were set, but failed to call BuildVisemeKeysFromPending: "
                                + call_info
                            )
                    else:
                        _warn(
                            "fallback aux viseme arrays failed: "
                            + aux_info
                            + " | BP should add arrays: "
                            + "PendingVisemeStartMs(int[]), PendingVisemeEndMs(int[]), "
                            + "PendingVisemeCurves(name[]/string[]), PendingVisemeWeights(float[])"
                        )
            else:
                set_ok, set_err = _try_set_prop(vis_target, vis_name, current_viseme_prop)
                if set_ok:
                    _log(f"set {vis_name} ({vis_scope}) via inplace update")
                    _log(info)
                else:
                    _warn(f"inplace updated but failed to set {vis_name}: {set_err}")
    elif args.apply_viseme:
        if not vis_name:
            _warn("skip viseme apply because VisemeKeys not resolved")
        else:
            vis_payload, field_map, template_fields = _build_viseme_dict_payload(
                viseme_curves, current_viseme_prop
            )
            _log(
                "viseme map="
                + f"start:{field_map['start']},end:{field_map['end']},"
                + f"curve:{field_map['curve']},weight:{field_map['weight']}"
            )
            if template_fields:
                _log("viseme template fields=" + ", ".join(template_fields))
            ok, set_err = _try_set_prop(vis_target, vis_name, vis_payload)
            if ok:
                _log(f"set {vis_name} ({vis_scope}) count={len(vis_payload)}")
            else:
                _warn(f"failed to set {vis_name}: {set_err}")
    else:
        _log("skip viseme apply (safe mode). use --apply-viseme-inplace to enable low-risk update.")

    turn_id = tracks.get("turn_id")
    _log(f"synced actor={actor.get_actor_label()} turn_id={turn_id}")

    if args.save_level:
        try:
            unreal.EditorLevelLibrary.save_current_level()
            _log("level saved")
        except Exception as exc:
            _warn(f"save level failed: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
