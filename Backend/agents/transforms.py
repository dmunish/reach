from typing import Dict, List

def transform_to_tree(data: List[Dict], config: Dict) -> List[Dict]:
    """
    Converts a flat list of rows into a hierarchical tree structure.
    Required for: tree, treemap, sunburst.
    """
    id_key = config.get("id_key", "id")
    parent_key = config.get("parent_key", "parent")
    name_key = config.get("name_key", "name")
    value_key = config.get("value_key", "value")

    # Build a lookup map
    lookup = {row[id_key]: {**row, "name": row.get(name_key), "children": []} for row in data}
    
    root_nodes = []

    for row in data:
        node = lookup[row[id_key]]
        parent_id = row.get(parent_key)
        
        # If there is a parent and it exists in our data, add as child
        if parent_id and parent_id in lookup:
            # Avoid adding self as child if data is messy
            if parent_id != row[id_key]:
                lookup[parent_id]["children"].append(node)
        else:
            # No parent -> Root node
            root_nodes.append(node)
            
    # Clean up empty children lists and map value if provided
    def clean_node(node):
        if not node["children"]:
            del node["children"]
        if value_key and value_key in node:
            node["value"] = node[value_key]
        return node

    return [clean_node(n) for n in root_nodes]

def transform_to_graph(data: List[Dict], config: Dict) -> Dict:
    """
    Converts a flat list of relationships (edges) into Graph format {nodes, links}.
    Required for: graph, graphGL, sankey.
    """
    source_key = config.get("source_key", "source")
    target_key = config.get("target_key", "target")
    value_key = config.get("value_key", "value")

    nodes_set = set()
    links = []

    for row in data:
        source_name = str(row.get(source_key))
        target_name = str(row.get(target_key))
        
        nodes_set.add(source_name)
        nodes_set.add(target_name)
        
        link = {"source": source_name, "target": target_name}
        if value_key in row:
            link["value"] = row[value_key]
        links.append(link)

    # ECharts requires nodes as a list of objects with 'name' property
    nodes = [{"name": name} for name in nodes_set]

    return {"nodes": nodes, "links": links}

def transform_to_matrix(data: List[Dict], config: Dict) -> List[List]:
    """
    Pivots data for Heatmaps. 
    Expects: [x_axis, y_axis, value] per row.
    Returns: [[x, y, value], ...] which is standard heatmap source format.
    """
    # In many cases, simple mapping is enough, but for completeness:
    x_key = config.get("x_key")
    y_key = config.get("y_key")
    v_key = config.get("v_key")
    
    if not (x_key and y_key and v_key):
        return data # Fallback

    return [[row[x_key], row[y_key], row[v_key]] for row in data]
