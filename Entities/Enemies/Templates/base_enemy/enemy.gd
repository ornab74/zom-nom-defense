extends CharacterBody3D

const CMP_EPSILON := 0.001
const MIN_MOVEMENT_SQUARED := 0.0025

@export_group("Movement")
@export var movement_speed: float = 2.0
@export var rotation_speed: float = PI / 3.0
@export var path_desired_distance: float = 0.35
@export var target_desired_distance: float = 2.0
@export var max_vertical_speed: float = 8.0
@export var floor_snap_distance: float = 0.8

@export_group("Navigation intelligence")
@export var repath_interval: float = 0.35
@export var target_refresh_interval: float = 1.25
@export var stuck_repath_seconds: float = 0.8
@export var stuck_retarget_seconds: float = 2.4
@export var target_move_threshold: float = 0.75
@export var enable_avoidance: bool = true
@export var avoidance_neighbor_distance: float = 5.0
@export var avoidance_max_neighbors: int = 8

@export_group("Combat")
@export var target_attack_range: float = 2.0
@export var survivor_group: String = "survivors"
@export var building_group: String = "buildings"
@export var building_attack_range: float = 6.0
@export var scrap_reward: int = 10
@export var xp_reward: int = 10
@export var enemy_type: String = "base_enemy"

@export_group("Animations")
@export var idle_animation: String = "zombie_library/zombie_idle"
@export var run_animation: String = "zombie_library/zombie_running"

var attack: Component_Attack
var health: Component_Health
var damage_numbers: Component_DamageNumbers

@onready var animation_player: AnimationPlayer = $AnimationPlayer
@onready var mesh_instance: MeshInstance3D = $characterMedium
@onready var navigation_agent: NavigationAgent3D = $NavigationAgent3D

var current_target: Node3D = null
var fallback_building_target: Node3D = null
var _last_requested_target_position := Vector3.INF
var _last_position := Vector3.ZERO
var _repath_clock := 0.0
var _target_refresh_clock := 0.0
var _stuck_clock := 0.0
var _reachability_check_pending := false
var _avoidance_velocity := Vector3.ZERO


func _ready() -> void:
  if has_meta("attack_component"):
    attack = get_meta("attack_component")
  if has_meta("health_component"):
    health = get_meta("health_component")
  if has_meta("damage_numbers_component"):
    damage_numbers = get_meta("damage_numbers_component")

  floor_snap_length = floor_snap_distance
  floor_max_angle = deg_to_rad(55.0)
  navigation_agent.path_desired_distance = path_desired_distance
  navigation_agent.target_desired_distance = target_desired_distance

  # Large path simplification values cut across stair switchbacks. Keep every
  # meaningful corner on multi-level geometry and let the navmesh guide ascent.
  navigation_agent.simplify_path = true
  navigation_agent.simplify_epsilon = 0.15
  navigation_agent.path_max_distance = 2.5
  navigation_agent.avoidance_enabled = enable_avoidance
  navigation_agent.neighbor_distance = avoidance_neighbor_distance
  navigation_agent.max_neighbors = avoidance_max_neighbors
  navigation_agent.radius = 0.55
  navigation_agent.height = 3.6
  navigation_agent.debug_enabled = ProjectSettings.get_setting("zom_nom_defense/debug/show_navigation_paths", false)

  if enable_avoidance and not navigation_agent.velocity_computed.is_connected(_on_safe_velocity_computed):
    navigation_agent.velocity_computed.connect(_on_safe_velocity_computed)

  if health:
    health.died.connect(_on_died)
    health.damaged.connect(_on_health_damaged)

  _last_position = global_position
  _actor_setup.call_deferred()


func load_resource(resource: Resource_EnemyType) -> void:
  ready.connect(func() -> void:
    MyLogger.debug("Enemy", "Loading enemy resource: %s" % resource.name)
    movement_speed = resource.speed
    target_desired_distance = resource.target_desired_distance
    target_attack_range = resource.target_attack_range
    building_attack_range = resource.building_attack_range
    scrap_reward = resource.scrap_reward
    xp_reward = resource.xp_reward
    enemy_type = resource.enemy_type

    if resource.skin_material and mesh_instance:
      mesh_instance.set_surface_override_material(0, resource.skin_material)

    navigation_agent.target_desired_distance = target_desired_distance
    scale = Vector3.ONE * resource.scale_multiplier

    if health:
      health.hitpoints = resource.hitpoints
      health.max_hitpoints = resource.hitpoints
      health._update_display()

    if attack:
      attack.damage_amount = resource.damage_amount
      attack.attack_speed = resource.attack_speed
      attack.damage_source = resource.enemy_type
      if resource.attack_effect:
        attack.attack_effect = resource.attack_effect
  , Object.CONNECT_ONE_SHOT)


func _actor_setup() -> void:
  await get_tree().physics_frame
  await get_tree().physics_frame
  _choose_target()
  _request_path_to_active_target(true)


func _choose_target() -> void:
  var targets := get_tree().get_nodes_in_group(survivor_group)
  var best_target: Node3D = null
  var best_score := INF

  for candidate in targets:
    if not candidate is Node3D or not is_instance_valid(candidate):
      continue
    var candidate_target := candidate as Node3D
    # Prefer nearby survivors while lightly penalizing vertical separation.
    # This creates predictable zombie pressure without every enemy selecting
    # the same random survivor on another floor.
    var delta := candidate_target.global_position - global_position
    var score := Vector2(delta.x, delta.z).length() + absf(delta.y) * 1.35
    if score < best_score:
      best_score = score
      best_target = candidate_target

  current_target = best_target
  fallback_building_target = null

  if current_target == null:
    if attack:
      attack.cancel()
    navigation_agent.target_position = global_position
    MyLogger.trace("Enemy", "No valid survivors available.")
  else:
    MyLogger.debug("Enemy", "Selected target: %s" % current_target.name)


func _active_navigation_target() -> Node3D:
  if fallback_building_target and is_instance_valid(fallback_building_target):
    return fallback_building_target
  if current_target and is_instance_valid(current_target):
    return current_target
  return null


func _request_path_to_active_target(force: bool = false) -> void:
  var active_target := _active_navigation_target()
  if active_target == null:
    return

  var destination := active_target.global_position
  if not force and destination.distance_to(_last_requested_target_position) < target_move_threshold:
    return

  _last_requested_target_position = destination
  navigation_agent.target_position = destination
  _queue_reachability_check()


func _queue_reachability_check() -> void:
  if _reachability_check_pending:
    return
  _reachability_check_pending = true
  _check_reachability_after_sync.call_deferred()


func _check_reachability_after_sync() -> void:
  await get_tree().physics_frame
  _reachability_check_pending = false

  if current_target == null or not is_instance_valid(current_target):
    return

  if navigation_agent.is_target_reachable():
    if fallback_building_target != null:
      fallback_building_target = null
      _last_requested_target_position = Vector3.INF
      _request_path_to_active_target(true)
    return

  var blocking_building := _find_building_closest_to_target()
  if blocking_building:
    fallback_building_target = blocking_building
    _last_requested_target_position = Vector3.INF
    navigation_agent.target_position = blocking_building.global_position
    MyLogger.info("Enemy.Navigation", "Primary route blocked; attacking obstacle %s" % blocking_building.name)


func _find_nearest_building_in_range() -> Node3D:
  var nearest_building: Node3D = null
  var nearest_distance := building_attack_range + 1.0

  for building in get_tree().get_nodes_in_group(building_group):
    if not building is Node3D or not is_instance_valid(building):
      continue
    var building_node := building as Node3D
    var distance := global_position.distance_to(building_node.global_position)
    if distance <= building_attack_range and distance < nearest_distance:
      nearest_distance = distance
      nearest_building = building_node

  return nearest_building


func _find_building_closest_to_target() -> Node3D:
  if current_target == null or not is_instance_valid(current_target):
    return null

  var closest_building: Node3D = null
  var closest_score := INF

  for building in get_tree().get_nodes_in_group(building_group):
    if not building is Node3D or not is_instance_valid(building):
      continue
    var building_node := building as Node3D
    var target_distance := building_node.global_position.distance_to(current_target.global_position)
    var zombie_distance := global_position.distance_to(building_node.global_position)
    var score := target_distance + zombie_distance * 0.2
    if score < closest_score:
      closest_score = score
      closest_building = building_node

  return closest_building


func _process(_delta: float) -> void:
  _attack_target()
  if velocity.length_squared() > 0.1:
    animation_player.play(run_animation)
  else:
    animation_player.play(idle_animation)


func _physics_process(delta: float) -> void:
  if NavigationServer3D.map_get_iteration_id(navigation_agent.get_navigation_map()) == 0:
    return

  _repath_clock += delta
  _target_refresh_clock += delta

  if _target_refresh_clock >= target_refresh_interval:
    _target_refresh_clock = 0.0
    if current_target == null or not is_instance_valid(current_target):
      _choose_target()
    _request_path_to_active_target()

  if _repath_clock >= repath_interval:
    _repath_clock = 0.0
    _request_path_to_active_target()

  _update_navigation(delta)
  move_and_slide()
  apply_floor_snap()
  _update_stuck_recovery(delta)


func _update_navigation(delta: float) -> void:
  if navigation_agent.is_navigation_finished():
    velocity = Vector3.ZERO
    return

  var next_path_position := navigation_agent.get_next_path_position()
  var path_delta := next_path_position - global_position

  # Preserve the path's vertical component. Flattening this vector is the
  # classic reason agents stop at stairs and ramps.
  var direction := path_delta.normalized()
  var desired_velocity := direction * movement_speed
  desired_velocity.y = clampf(desired_velocity.y, -max_vertical_speed, max_vertical_speed)

  if enable_avoidance:
    navigation_agent.velocity = desired_velocity
    velocity = _avoidance_velocity if _avoidance_velocity.length_squared() > CMP_EPSILON else desired_velocity
  else:
    velocity = desired_velocity

  var horizontal_look := Vector3(next_path_position.x, global_position.y, next_path_position.z)
  _rotate_toward(horizontal_look, delta)


func _rotate_toward(global_look_position: Vector3, delta: float) -> void:
  var local_target := to_local(global_look_position)
  local_target.y = 0.0
  if local_target.length_squared() <= CMP_EPSILON * CMP_EPSILON:
    return

  var current_forward := Vector3.MODEL_FRONT
  var target_forward := local_target.normalized()
  var radians_to_target := current_forward.angle_to(target_forward)
  if radians_to_target <= CMP_EPSILON:
    return

  var fraction := clampf((rotation_speed * delta) / radians_to_target, 0.0, 1.0)
  var interpolated := to_global(current_forward.slerp(target_forward, fraction))
  look_at(interpolated, Vector3.UP, true)


func _on_safe_velocity_computed(safe_velocity: Vector3) -> void:
  # RVO avoidance is primarily horizontal; retain stair-climbing intent from
  # the requested path so crowds do not pin one another at stair entrances.
  safe_velocity.y = navigation_agent.velocity.y
  _avoidance_velocity = safe_velocity


func _update_stuck_recovery(delta: float) -> void:
  var moved_squared := global_position.distance_squared_to(_last_position)
  var trying_to_move := not navigation_agent.is_navigation_finished() and velocity.length_squared() > 0.1

  if trying_to_move and moved_squared < MIN_MOVEMENT_SQUARED:
    _stuck_clock += delta
  else:
    _stuck_clock = maxf(0.0, _stuck_clock - delta * 2.0)

  if _stuck_clock >= stuck_retarget_seconds:
    _stuck_clock = 0.0
    _choose_target()
    _last_requested_target_position = Vector3.INF
    _request_path_to_active_target(true)
    MyLogger.info("Enemy.Navigation", "Recovered stalled agent by selecting a fresh route")
  elif _stuck_clock >= stuck_repath_seconds:
    _last_requested_target_position = Vector3.INF
    _request_path_to_active_target(true)

  _last_position = global_position


func _attack_target() -> void:
  if current_target == null or not is_instance_valid(current_target):
    _choose_target()
    if current_target == null:
      return

  if fallback_building_target and is_instance_valid(fallback_building_target):
    if global_position.distance_to(fallback_building_target.global_position) <= building_attack_range:
      attack.perform_attack(fallback_building_target)
      return

  if global_position.distance_to(current_target.global_position) <= target_attack_range:
    attack.perform_attack(current_target)
    return

  var nearby_building := _find_nearest_building_in_range()
  if nearby_building:
    attack.perform_attack(nearby_building)


func _on_died(damage_source: String = "unknown") -> void:
  MyLogger.info("Enemy", "Enemy (%s) died from %s, removing from scene" % [enemy_type, damage_source])
  if StatsManager:
    StatsManager.track_enemy_defeated(enemy_type, damage_source == "player")
  CurrencyManager.earn_xp(xp_reward)
  if scrap_reward > 0:
    CurrencyManager.earn_scrap(scrap_reward)
    if damage_numbers:
      damage_numbers.show_scrap(scrap_reward)
  queue_free()


func _on_health_damaged(amount: int, hitpoints: int, damage_source: String = "unknown") -> void:
  MyLogger.debug("Enemy.Combat", "Enemy (%s) took %d damage from %s. Remaining HP: %d" % [enemy_type, amount, damage_source, hitpoints])
