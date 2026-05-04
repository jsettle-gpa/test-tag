SELECT
    equipment_id,
    equipment_name,
    equipment_path,
    parent_equipment_id,
    equipment_type_id,
    equipment_type_name,
    equipment_enabled,
    hierarchy_depth,
    has_children,
    state_mode,
    count_mode,
    is_key_cell
FROM core.v_equipment_tree_plus
ORDER BY equipment_path;
