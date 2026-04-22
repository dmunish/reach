from typing import Dict, List

def _list_to_dicts(data: List[List]) -> List[Dict]:
    """Helper to convert tabular [headers, *rows] back to list of dicts."""
    if not data or len(data) < 2:
        return []
    headers = data[0]
    return [dict(zip(headers, row)) for row in data[1:]]

def transform_to_tree(data: List[Dict], config: Dict) -> List[Dict]:
    """
    Converts a flat list of rows into a hierarchical tree structure.
    Required for: tree, treemap, sunburst.
    """
    data = _list_to_dicts(data)
    
    id_key = config.get("id_key", "id")
    parent_key = config.get("parent_key", "parent")
    name_key = config.get("name_key", "name")
    value_key = config.get("value_key", "value")

    lookup = {row[id_key]: {**row, "name": row.get(name_key), "children": []} for row in data}
    root_nodes = []

    for row in data:
        node = lookup[row[id_key]]
        parent_id = row.get(parent_key)
        
        if parent_id and parent_id in lookup:
            if parent_id != row[id_key]:
                lookup[parent_id]["children"].append(node)
        else:
            root_nodes.append(node)
            
    # CRITICAL: Recursive clean up
    def clean_node(node):
        if not node.get("children"):
            node.pop("children", None)
        else:
            # Recursively clean children
            node["children"] = [clean_node(child) for child in node["children"]]
            
        if value_key and value_key in node:
            node["value"] = node[value_key]
            
        return node

    return [clean_node(n) for n in root_nodes]

def transform_to_graph(data: List[Dict], config: Dict) -> Dict:
    """
    Converts a flat list of relationships (edges) into Graph format {nodes, links}.
    Required for: graph, graphGL, sankey.
    """
    if not data or len(data) < 2:
        return {"nodes": [], "links": []}
        
    headers = data[0]
    source_idx = headers.index(config.get("source_key", "source"))
    target_idx = headers.index(config.get("target_key", "target"))
    
    value_key = config.get("value_key", "value")
    value_idx = headers.index(value_key) if value_key in headers else None

    nodes_set = set()
    links = []

    for row in data[1:]:
        source_name = str(row[source_idx])
        target_name = str(row[target_idx])
        
        nodes_set.add(source_name)
        nodes_set.add(target_name)
        
        link = {"source": source_name, "target": target_name}
        if value_idx is not None:
            link["value"] = row[value_idx]
        links.append(link)

    nodes = [{"name": name} for name in nodes_set]
    return {"nodes": nodes, "links": links}

def transform_to_matrix(data: List[Dict], config: Dict) -> List[List]:
    """
    Pivots data for Heatmaps. 
    Expects: [x_axis, y_axis, value] per row.
    Returns: [[x, y, value], ...] which is standard heatmap source format.
    """
    if not data or len(data) < 2:
        return []
        
    headers = data[0]
    try:
        x_idx = headers.index(config.get("x_key"))
        y_idx = headers.index(config.get("y_key"))
        v_idx = headers.index(config.get("v_key"))
    except ValueError:
        return data # Fallback if keys don't match

    # List comprehension using indices instead of dict keys
    return [[row[x_idx], row[y_idx], row[v_idx]] for row in data[1:]]
