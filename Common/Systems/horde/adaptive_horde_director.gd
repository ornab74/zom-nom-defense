extends Node
class_name AdaptiveHordeDirector

## Adaptive encounter director for authored and procedural scenarios.
##
## The director does not spawn arbitrary enemies everywhere. Scenario authors add
## HordeSpawnPoint nodes to groups such as `horde_spawn_ground`,
## `horde_spawn_roof`, `horde_spawn_pool`, and `horde_spawn_interior`. The
## director scores those points against current player pressure, visibility,
## route diversity, and recent use, then emits a wave plan for the scenario's
## existing spawner to execute.

signal wave_planned(wave_index: int, plan: Dictionary)
signal pressure_changed(previous: float, current: float)
signal intensity_band_changed(previous: StringName, current: StringName)
signal spawn_request(enemy_id: StringName, spawn_point: Node3D, modifiers: Dictionary)
signal lull_started(duration: float)
signal lull_finished

@export_group("Pacing")
@export_range(0.0, 1.0, 0.01) var starting_pressure: float = 0.18
@export_range(0.0, 1.0, 0.01) var pressure_gain_per_second: float = 0.008
@export_range(0.0, 1.0, 0.01) var pressure_decay_per_kill: float = 0.014
@export_range(0.0, 1.0, 0.01) var survivor_damage_pressure: float = 0.035
@export_range(1.0, 60.0, 0.5) var minimum_lull_seconds: float = 5.0
@export_range(1.0, 90.0, 0.5) var maximum_lull_seconds: float = 14.0
@export_range(5.0, 120.0, 1.0) var target_wave_duration: float = 38.0

@export_group("Wave Shape")
@export_range(1, 300, 1) var base_budget: int = 14
@export_range(0.0, 10.0, 0.1) var budget_growth_per_wave: float = 2.4
@export_range(1, 80, 1) var maximum_concurrent_enemies: int = 42
@export_range(0.1, 8.0, 0.1) var minimum_spawn_interval: float = 0.45
@export_range(0.1, 12.0, 0.1) var maximum_spawn_interval: float = 2.2
@export var deterministic_seed: int = 1337

@export_group("Spatial Fairness")
@export_range(1.0, 100.0, 0.5) var minimum_spawn_distance: float = 15.0
@export_range(1.0, 200.0, 0.5) var preferred_spawn_distance: float = 34.0
@export_range(0.0, 60.0, 0.5) var recent_spawn_cooldown: float = 18.0
@export_range(0.0, 1.0, 0.05) var hidden_spawn_bonus: float = 0.3
@export_range(0.0, 1.0, 0.05) var route_diversity_bonus: float = 0.25
@export_range(0.0, 1.0, 0.05) var vertical_route_bonus: float = 0.15

@export_group("Roster")
@export var grunt_id: StringName = &"zombie_grunt"
@export var runner_id: StringName = &"zombie_runner"
@export var climber_id: StringName = &"zombie_climber"
@export var brute_id: StringName = &"zombie_brute"
@export var crawler_id: StringName = &"zombie_crawler"
@export var screecher_id: StringName = &"zombie_screecher"
@export var spitter_id: StringName = &"zombie_spitter"
@export var swimmer_id: StringName = &"zombie_swimmer"

const BAND_CALM: StringName = &"calm"
const BAND_BUILDING: StringName = &"building"
const BAND_HIGH: StringName = &"high"
const BAND_CRISIS: StringName = &"crisis"

var pressure: float = 0.0
var wave_index: int = 0
var active_enemy_count: int = 0
var current_band: StringName = BAND_CALM
var _rng := RandomNumberGenerator.new()
var _recent_spawn_time: Dictionary = {}
var _spawn_history: Array[Dictionary] = []
var _in_lull: bool = false
var _lull_remaining: float = 0.0
var _elapsed: float = 0.0
var _performance_samples: Array[Dictionary] = []


func _ready() -> void:
    _rng.seed = deterministic_seed
    pressure = starting_pressure
    current_band = _band_for_pressure(pressure)


func _process(delta: float) -> void:
    _elapsed += delta
    _age_spawn_cooldowns(delta)

    if _in_lull:
        _lull_remaining -= delta
        if _lull_remaining <= 0.0:
            _in_lull = false
            lull_finished.emit()
        return

    set_pressure(pressure + pressure_gain_per_second * delta)


func register_enemy_spawned() -> void:
    active_enemy_count += 1


func register_enemy_removed(was_killed: bool = true) -> void:
    active_enemy_count = maxi(0, active_enemy_count - 1)
    if was_killed:
        set_pressure(pressure - pressure_decay_per_kill)


func register_survivor_damage(damage_fraction: float) -> void:
    set_pressure(pressure + survivor_damage_pressure * clampf(damage_fraction, 0.0, 1.0))


func record_performance_sample(
    elapsed_seconds: float,
    kills: int,
    survivor_health_fraction: float,
    resources_fraction: float,
    defenses_destroyed: int
) -> void:
    var sample := {
        "elapsed": maxf(0.01, elapsed_seconds),
        "kills": maxi(0, kills),
        "health": clampf(survivor_health_fraction, 0.0, 1.0),
        "resources": clampf(resources_fraction, 0.0, 1.0),
        "defenses_destroyed": maxi(0, defenses_destroyed),
    }
    _performance_samples.append(sample)
    if _performance_samples.size() > 8:
        _performance_samples.pop_front()


func set_pressure(value: float) -> void:
    var previous := pressure
    pressure = clampf(value, 0.0, 1.0)
    if not is_equal_approx(previous, pressure):
        pressure_changed.emit(previous, pressure)

    var next_band := _band_for_pressure(pressure)
    if next_band != current_band:
        var previous_band := current_band
        current_band = next_band
        intensity_band_changed.emit(previous_band, current_band)


func plan_next_wave(scenario_tags: Array[StringName] = []) -> Dictionary:
    wave_index += 1
    var budget := _calculate_wave_budget()
    var composition := _compose_roster(budget, scenario_tags)
    var spawn_points := _collect_spawn_points(scenario_tags)
    var route_plan := _assign_spawn_routes(composition, spawn_points)
    var interval := lerpf(maximum_spawn_interval, minimum_spawn_interval, pressure)
    var plan := {
        "wave_index": wave_index,
        "pressure": pressure,
        "intensity_band": current_band,
        "budget": budget,
        "spawn_interval": interval,
        "target_duration": target_wave_duration,
        "maximum_concurrent": maximum_concurrent_enemies,
        "composition": composition,
        "routes": route_plan,
        "scenario_tags": scenario_tags,
        "seed": _rng.seed,
    }
    wave_planned.emit(wave_index, plan)
    return plan


func execute_plan(plan: Dictionary) -> void:
    var interval := float(plan.get("spawn_interval", 1.0))
    for route in plan.get("routes", []):
        while active_enemy_count >= maximum_concurrent_enemies:
            await get_tree().create_timer(0.25).timeout
        var point := route.get("spawn_point") as Node3D
        if not is_instance_valid(point):
            continue
        var enemy_id := StringName(route.get("enemy_id", grunt_id))
        var modifiers: Dictionary = route.get("modifiers", {})
        spawn_request.emit(enemy_id, point, modifiers)
        register_enemy_spawned()
        _mark_spawn_used(point)
        await get_tree().create_timer(interval * _rng.randf_range(0.82, 1.18)).timeout

    begin_lull(_calculate_lull_duration())


func begin_lull(duration: float = -1.0) -> void:
    _in_lull = true
    _lull_remaining = duration if duration >= 0.0 else _calculate_lull_duration()
    lull_started.emit(_lull_remaining)


func _calculate_wave_budget() -> int:
    var growth := base_budget + roundi((wave_index - 1) * budget_growth_per_wave)
    var pressure_multiplier := lerpf(0.82, 1.42, pressure)
    var performance_multiplier := _performance_multiplier()
    return maxi(1, roundi(growth * pressure_multiplier * performance_multiplier))


func _performance_multiplier() -> float:
    if _performance_samples.is_empty():
        return 1.0
    var score := 0.0
    for sample in _performance_samples:
        var kills_per_minute := float(sample["kills"]) / float(sample["elapsed"]) * 60.0
        score += clampf(kills_per_minute / 24.0, 0.0, 1.0) * 0.35
        score += float(sample["health"]) * 0.35
        score += float(sample["resources"]) * 0.2
        score -= clampf(float(sample["defenses_destroyed"]) / 5.0, 0.0, 1.0) * 0.25
    score /= _performance_samples.size()
    return lerpf(0.76, 1.28, clampf(score, 0.0, 1.0))


func _compose_roster(budget: int, scenario_tags: Array[StringName]) -> Array[Dictionary]:
    var roster := _available_roster(scenario_tags)
    var result: Array[Dictionary] = []
    var remaining := budget
    var safety := 0
    while remaining > 0 and safety < 1000:
        safety += 1
        var candidates := roster.filter(func(entry: Dictionary) -> bool: return int(entry["cost"]) <= remaining)
        if candidates.is_empty():
            break
        var selected := _weighted_pick(candidates)
        result.append({
            "enemy_id": selected["id"],
            "cost": selected["cost"],
            "role": selected["role"],
            "modifiers": _roll_enemy_modifiers(StringName(selected["id"])),
        })
        remaining -= int(selected["cost"])
    return result


func _available_roster(scenario_tags: Array[StringName]) -> Array[Dictionary]:
    var roster: Array[Dictionary] = [
        {"id": grunt_id, "cost": 1, "weight": 9.0, "role": &"pressure"},
        {"id": runner_id, "cost": 2, "weight": 3.4 + pressure * 3.0, "role": &"flanker"},
        {"id": crawler_id, "cost": 2, "weight": 2.0, "role": &"low_route"},
    ]
    if wave_index >= 2:
        roster.append({"id": climber_id, "cost": 3, "weight": 2.4, "role": &"vertical"})
    if wave_index >= 3:
        roster.append({"id": screecher_id, "cost": 4, "weight": 1.2, "role": &"support"})
    if wave_index >= 4:
        roster.append({"id": spitter_id, "cost": 4, "weight": 1.0, "role": &"ranged"})
    if wave_index >= 5:
        roster.append({"id": brute_id, "cost": 7, "weight": 0.8 + pressure, "role": &"breaker"})
    if scenario_tags.has(&"pool_party") and wave_index >= 2:
        roster.append({"id": swimmer_id, "cost": 3, "weight": 2.2, "role": &"water_route"})
    return roster


func _weighted_pick(entries: Array) -> Dictionary:
    var total := 0.0
    for entry in entries:
        total += maxf(0.0, float(entry["weight"]))
    var cursor := _rng.randf() * total
    for entry in entries:
        cursor -= maxf(0.0, float(entry["weight"]))
        if cursor <= 0.0:
            return entry
    return entries.back()


func _roll_enemy_modifiers(enemy_id: StringName) -> Dictionary:
    var modifiers := {
        "health_scale": lerpf(0.92, 1.24, pressure),
        "speed_scale": lerpf(0.96, 1.15, pressure),
        "damage_scale": lerpf(0.92, 1.18, pressure),
        "visual_seed": _rng.randi(),
    }
    if enemy_id == climber_id:
        modifiers["prefer_vertical_routes"] = true
    elif enemy_id == brute_id:
        modifiers["prefer_barricades"] = true
    elif enemy_id == swimmer_id:
        modifiers["prefer_water_routes"] = true
    return modifiers


func _collect_spawn_points(scenario_tags: Array[StringName]) -> Array[Node3D]:
    var result: Array[Node3D] = []
    var groups: Array[StringName] = [&"horde_spawn_ground", &"horde_spawn_interior"]
    if scenario_tags.has(&"vertical_house"):
        groups.append(&"horde_spawn_roof")
    if scenario_tags.has(&"pool_party"):
        groups.append(&"horde_spawn_pool")
    if scenario_tags.has(&"highway"):
        groups.append(&"horde_spawn_road")
    for group in groups:
        for node in get_tree().get_nodes_in_group(group):
            if node is Node3D and not result.has(node):
                result.append(node)
    return result


func _assign_spawn_routes(composition: Array[Dictionary], points: Array[Node3D]) -> Array[Dictionary]:
    var routes: Array[Dictionary] = []
    var used_route_tags: Dictionary = {}
    for entry in composition:
        var point := _select_spawn_point(points, StringName(entry["role"]), used_route_tags)
        if not is_instance_valid(point):
            continue
        var route_tag := StringName(point.get_meta("route_tag", "default"))
        used_route_tags[route_tag] = int(used_route_tags.get(route_tag, 0)) + 1
        routes.append({
            "enemy_id": entry["enemy_id"],
            "spawn_point": point,
            "spawn_path": point.get_path(),
            "route_tag": route_tag,
            "modifiers": entry["modifiers"],
        })
    return routes


func _select_spawn_point(points: Array[Node3D], role: StringName, used_route_tags: Dictionary) -> Node3D:
    var target := _primary_defense_target()
    var best_point: Node3D
    var best_score := -INF
    for point in points:
        var score := _score_spawn_point(point, target, role, used_route_tags)
        if score > best_score:
            best_score = score
            best_point = point
    return best_point


func _score_spawn_point(point: Node3D, target: Node3D, role: StringName, used_route_tags: Dictionary) -> float:
    var score := _rng.randf_range(-0.08, 0.08)
    var distance := preferred_spawn_distance
    if is_instance_valid(target):
        distance = point.global_position.distance_to(target.global_position)
        if distance < minimum_spawn_distance:
            return -1000.0
        score += 1.0 - minf(absf(distance - preferred_spawn_distance) / preferred_spawn_distance, 1.0)

    var cooldown := float(_recent_spawn_time.get(point.get_instance_id(), 0.0))
    score -= clampf(cooldown / maxf(0.01, recent_spawn_cooldown), 0.0, 1.0) * 0.8
    if bool(point.get_meta("hidden_from_start", false)):
        score += hidden_spawn_bonus

    var route_tag := StringName(point.get_meta("route_tag", "default"))
    score += route_diversity_bonus / (1.0 + int(used_route_tags.get(route_tag, 0)))

    var point_type := StringName(point.get_meta("spawn_type", "ground"))
    if role == &"vertical" and point_type in [&"roof", &"upper", &"balcony"]:
        score += vertical_route_bonus + 0.35
    if role == &"water_route" and point_type == &"pool":
        score += 0.65
    if role == &"low_route" and point_type in [&"crawl", &"drain"]:
        score += 0.45
    return score


func _primary_defense_target() -> Node3D:
    var candidates := get_tree().get_nodes_in_group("survivor")
    for candidate in candidates:
        if candidate is Node3D:
            return candidate
    candidates = get_tree().get_nodes_in_group("defense_objective")
    for candidate in candidates:
        if candidate is Node3D:
            return candidate
    return null


func _mark_spawn_used(point: Node3D) -> void:
    _recent_spawn_time[point.get_instance_id()] = recent_spawn_cooldown
    _spawn_history.append({"time": _elapsed, "path": point.get_path()})
    if _spawn_history.size() > 128:
        _spawn_history.pop_front()


func _age_spawn_cooldowns(delta: float) -> void:
    for key in _recent_spawn_time.keys():
        var remaining := maxf(0.0, float(_recent_spawn_time[key]) - delta)
        if remaining <= 0.0:
            _recent_spawn_time.erase(key)
        else:
            _recent_spawn_time[key] = remaining


func _calculate_lull_duration() -> float:
    var crisis_shortening := lerpf(1.0, 0.55, pressure)
    return _rng.randf_range(minimum_lull_seconds, maximum_lull_seconds) * crisis_shortening


func _band_for_pressure(value: float) -> StringName:
    if value < 0.28:
        return BAND_CALM
    if value < 0.56:
        return BAND_BUILDING
    if value < 0.82:
        return BAND_HIGH
    return BAND_CRISIS
