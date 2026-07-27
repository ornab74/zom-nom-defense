extends Node3D
class_name MultiLevelController

## Coordinates visibility, selection, and navigation for stacked playable floors.
## Add each floor root to the `playable_floor` group and set its `floor_index`
## metadata. Navigation geometry remains active while hidden so zombies can keep
## travelling through stairs between floors.

signal floor_changed(previous_floor: int, current_floor: int)
signal floor_transition_requested(from_floor: int, to_floor: int)

@export var starting_floor: int = 0
@export var dim_inactive_floors: bool = true
@export_range(0.0, 1.0, 0.05) var inactive_floor_alpha: float = 0.18
@export var hide_floors_above: bool = true
@export var hide_floors_below: bool = false

var current_floor: int = 0
var _floors: Dictionary = {}


func _ready() -> void:
  _discover_floors()
  set_floor(starting_floor, true)


func _discover_floors() -> void:
  _floors.clear()
  for node in get_tree().get_nodes_in_group("playable_floor"):
    if not node is Node3D:
      continue
    var index := int(node.get_meta("floor_index", 0))
    _floors[index] = node


func get_floor_count() -> int:
  return _floors.size()


func get_available_floors() -> Array[int]:
  var result: Array[int] = []
  for key in _floors.keys():
    result.append(int(key))
  result.sort()
  return result


func floor_up() -> void:
  set_floor(_find_next_floor(1))


func floor_down() -> void:
  set_floor(_find_next_floor(-1))


func set_floor(index: int, immediate: bool = false) -> void:
  if not _floors.has(index):
    return
  if index == current_floor and not immediate:
    return

  var previous := current_floor
  floor_transition_requested.emit(previous, index)
  current_floor = index
  _apply_floor_presentation()
  floor_changed.emit(previous, current_floor)


func _find_next_floor(direction: int) -> int:
  var available := get_available_floors()
  if available.is_empty():
    return current_floor

  var current_position := available.find(current_floor)
  if current_position < 0:
    return available[0]

  return available[clampi(current_position + direction, 0, available.size() - 1)]


func _apply_floor_presentation() -> void:
  for index in _floors:
    var floor_root := _floors[index] as Node3D
    var should_hide := (hide_floors_above and index > current_floor) or (hide_floors_below and index < current_floor)
    floor_root.visible = not should_hide

    # Do not disable collisions or NavigationRegion3D nodes here. Keeping them
    # active is essential for enemies to traverse stairs while another floor is
    # selected by the player.
    if not should_hide and dim_inactive_floors:
      _set_floor_fade(floor_root, 1.0 if index == current_floor else inactive_floor_alpha)


func _set_floor_fade(root: Node, alpha: float) -> void:
  for child in root.get_children():
    if child is GeometryInstance3D:
      var geometry := child as GeometryInstance3D
      geometry.transparency = 1.0 - alpha
    _set_floor_fade(child, alpha)
