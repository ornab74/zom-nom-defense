extends Node3D
class_name ProceduralMapDresser

## Deterministically dresses authored maps without replacing their intentional
## combat layout. Place child Marker3D nodes in the `detail_spawn_zone` group,
## assign a rectangular `zone_size` metadata Vector2, and provide scene pools.

@export var seed: int = 1337
@export_range(0, 128, 1) var props_per_zone: int = 18
@export var minimum_spacing: float = 2.5
@export var edge_padding: float = 1.0
@export var random_y_rotation: bool = true
@export var random_scale_range := Vector2(0.9, 1.12)
@export var prop_scenes: Array[PackedScene] = []
@export var decal_scenes: Array[PackedScene] = []
@export var regenerate_in_editor: bool = false

var _generated_root: Node3D
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
  _generated_root = Node3D.new()
  _generated_root.name = "GeneratedMapDetails"
  add_child(_generated_root)
  generate()


func generate() -> void:
  clear_generated()
  if prop_scenes.is_empty() and decal_scenes.is_empty():
    return

  _rng.seed = seed
  for zone in get_tree().get_nodes_in_group("detail_spawn_zone"):
    if zone is Marker3D:
      _dress_zone(zone)


func clear_generated() -> void:
  if _generated_root == null:
    return
  for child in _generated_root.get_children():
    child.queue_free()


func _dress_zone(zone: Marker3D) -> void:
  var zone_size: Vector2 = zone.get_meta("zone_size", Vector2(12.0, 12.0))
  var accepted: Array[Vector3] = []
  var attempts := props_per_zone * 12

  while accepted.size() < props_per_zone and attempts > 0:
    attempts -= 1
    var local_point := Vector3(
      _rng.randf_range(-zone_size.x * 0.5 + edge_padding, zone_size.x * 0.5 - edge_padding),
      0.0,
      _rng.randf_range(-zone_size.y * 0.5 + edge_padding, zone_size.y * 0.5 - edge_padding)
    )
    var world_point := zone.to_global(local_point)

    if not _is_spaced(world_point, accepted):
      continue

    var scene := _pick_scene()
    if scene == null:
      return

    var instance := scene.instantiate()
    if not instance is Node3D:
      instance.queue_free()
      continue

    var prop := instance as Node3D
    _generated_root.add_child(prop)
    prop.global_position = world_point
    if random_y_rotation:
      prop.rotation.y = _rng.randf_range(0.0, TAU)
    var uniform_scale := _rng.randf_range(random_scale_range.x, random_scale_range.y)
    prop.scale = Vector3.ONE * uniform_scale
    accepted.append(world_point)


func _pick_scene() -> PackedScene:
  var pool: Array[PackedScene] = []
  pool.append_array(prop_scenes)
  pool.append_array(decal_scenes)
  if pool.is_empty():
    return null
  return pool[_rng.randi_range(0, pool.size() - 1)]


func _is_spaced(point: Vector3, accepted: Array[Vector3]) -> bool:
  for existing in accepted:
    if Vector2(point.x, point.z).distance_to(Vector2(existing.x, existing.z)) < minimum_spacing:
      return false
  return true
