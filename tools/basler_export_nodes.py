"""
Basler Camera - Export all writable nodes to XML or YAML
Requires: pypylon (pip install pypylon)

Connects to the first available Basler camera, inspects every node in the
NodeMap, and writes a structured XML or YAML file containing all accessible
parameters with their types, current values, and valid options/ranges.

Usage:
    python basler_export_nodes.py                          # all nodes, XML (default)
    python basler_export_nodes.py --format yaml            # all nodes, YAML
    python basler_export_nodes.py --capture-only           # image/capture nodes only, XML
    python basler_export_nodes.py --capture-only -f yaml   # image/capture nodes only, YAML
    python basler_export_nodes.py --format xml -o cam.xml
    python basler_export_nodes.py --format yaml -o cam.yaml
"""

import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pypylon import pylon, genicam


# ---------------------------------------------------------------------------
# Category filter for image/capture-relevant settings
# ---------------------------------------------------------------------------

# GenICam / Basler top-level category names that relate to image and video capture.
# All other categories (transport, device info, file access, I/O lines, etc.) are
# excluded when --capture-only is passed.
CAPTURE_CATEGORIES = {
    # --- Core image capture settings (confirmed from camera tree) ---
    "Image Format Control",           # Width, height, pixel format, binning, ROI
    "ImageFormatControl",
    "Acquisition Control",            # Exposure, frame rate, trigger, acquisition mode
    "AcquisitionControl",
    "Analog Control",                 # Gain, black level, gamma
    "AnalogControl",
    "Auto Function Control",          # Auto-exposure / auto-gain limits
    "AutoFunctionControl",
    "Auto Function ROI Control",      # Region used for auto functions
    "AutoFunctionROIControl",
    "Image Processing Control",       # Sharpness, noise reduction
    "ImageProcessingControl",
    # --- Colour cameras only ---
    "White Balance Control",
    "WhiteBalanceControl",
    "Color Transformation Control",
    "ColorTransformationControl",
    "Color Adjustment Control",       # Per-channel hue/saturation
    "ColorAdjustmentControl",
    "LUT Control",                    # Lookup table / tone curve
    "LUTControl",
    # --- Sensor quality ---
    "Static Defect Pixel Correction",
    "BslStaticDefectPixelCorrection",
}


# ---------------------------------------------------------------------------
# Node inspection
# ---------------------------------------------------------------------------

def _build_api_snippet(name: str, node_type: str, options: list = None) -> dict:
    """Return a dict of pypylon API call snippets for reading and writing a node."""
    read  = f"camera.{name}.Value"

    if node_type == "Command":
        return {
            "execute": f"camera.{name}.Execute()",
            "note": "Command nodes are executed, not set.",
        }
    if node_type == "Enumeration":
        result = {
            "get": read,
            "set": f'camera.{name}.Value = "<option>"',
            "set_int": f"camera.{name}.SetIntValue(<int>)",
        }
        if options:
            result["options"] = "[" + ", ".join(f'"{o}"' for o in options) + "]"
        return result
    if node_type == "Boolean":
        return {
            "get": read,
            "set": f"camera.{name}.Value = True  # or False",
        }

    # Integer, Float, String
    return {
        "get": read,
        "set": f"camera.{name}.Value = <value>",
    }


def get_node_info(node) -> dict | None:
    """
    Extract full information from a GenICam node.
    Returns a dict or None if the node is not accessible.
    """
    try:
        if not genicam.IsAvailable(node):
            return None
        if not genicam.IsWritable(node) and not genicam.IsReadable(node):
            return None

        info = {
            "name": node.Node.Name,
            "display_name": node.Node.DisplayName,
            "description": node.Node.Description.strip(),
            "access": "ReadWrite" if genicam.IsWritable(node) else "ReadOnly",
            "type": None,
            "current_value": None,
            "options": [],
            "min": None,
            "max": None,
            "unit": None,
            "increment": None,
            "category": "General",
            "pypylon_api": None,   # filled in below once type is known
        }

        node_type = node.Node.GetPrincipalInterfaceType()
        name = node.Node.Name

        if node_type == genicam.intfIEnumeration:
            info["type"] = "Enumeration"
            try:
                info["current_value"] = node.GetCurrentEntry().SymbolicName
            except Exception:
                info["current_value"] = "N/A"

            # Try every known way pypylon exposes enum entries
            options = []
            try:
                # Most common: node.Entries (list of IEnumEntry objects)
                options = [
                    e.SymbolicName for e in node.Entries
                    if genicam.IsAvailable(e) and e.SymbolicName != ""
                ]
            except Exception:
                pass

            if not options:
                try:
                    # Alternative: node.GetEntries()
                    options = [
                        e.SymbolicName for e in node.GetEntries()
                        if genicam.IsAvailable(e) and e.SymbolicName != ""
                    ]
                except Exception:
                    pass

            if not options:
                try:
                    # Fallback: node.Symbolics is a tuple of strings directly
                    options = list(node.Symbolics)
                except Exception:
                    pass

            info["options"] = options
            info["pypylon_api"] = _build_api_snippet(name, "Enumeration", options)

        elif node_type == genicam.intfIInteger:
            info["type"] = "Integer"
            info["pypylon_api"] = _build_api_snippet(name, "Integer")
            try:
                info["current_value"] = str(node.GetValue())
                info["min"] = str(node.Min)
                info["max"] = str(node.Max)
                info["increment"] = str(node.Inc)
            except Exception:
                pass

        elif node_type == genicam.intfIFloat:
            info["type"] = "Float"
            info["pypylon_api"] = _build_api_snippet(name, "Float")
            try:
                info["current_value"] = str(node.GetValue())
                info["min"] = str(node.Min)
                info["max"] = str(node.Max)
                info["unit"] = node.Unit if node.Unit else ""
            except Exception:
                pass

        elif node_type == genicam.intfIBoolean:
            info["type"] = "Boolean"
            info["pypylon_api"] = _build_api_snippet(name, "Boolean")
            try:
                info["current_value"] = str(node.GetValue())
                info["options"] = ["True", "False"]
            except Exception:
                pass

        elif node_type == genicam.intfIString:
            info["type"] = "String"
            info["pypylon_api"] = _build_api_snippet(name, "String")
            try:
                info["current_value"] = node.GetValue()
            except Exception:
                pass

        elif node_type == genicam.intfICommand:
            info["type"] = "Command"
            info["pypylon_api"] = _build_api_snippet(name, "Command")
            info["current_value"] = "(executable command)"

        else:
            return None

        return info

    except Exception:
        return None



def _node_name(obj) -> str:
    """Get Name from an ICategory (via .Node) or raw INode."""
    try:
        return obj.Node.Name
    except AttributeError:
        return obj.Name


def _node_display_name(obj) -> str:
    """Get DisplayName from an ICategory (via .Node) or raw INode."""
    try:
        return obj.Node.DisplayName
    except AttributeError:
        return obj.DisplayName


def _node_is_available(obj) -> bool:
    try:
        return genicam.IsAvailable(obj.Node)
    except AttributeError:
        return genicam.IsAvailable(obj)


def _node_interface_type(obj) -> int:
    """Return GetPrincipalInterfaceType() from ICategory (.Node) or raw INode."""
    try:
        return obj.Node.GetPrincipalInterfaceType()
    except AttributeError:
        return obj.GetPrincipalInterfaceType()


def _is_category(obj) -> bool:
    try:
        return _node_interface_type(obj) == genicam.intfICategory
    except Exception:
        return False


def _category_children(obj):
    """Yield children of a category node — not used in main path but kept for debug_tree."""
    try:
        for child in obj:
            yield child
        return
    except TypeError:
        pass
    try:
        for child in obj.GetChildren():
            yield child
    except Exception:
        pass


def build_category_map(node_map) -> dict[str, str]:
    """Build a {node_name: top_level_category_display_name} map.

    ICategory exposes children via .GetFeatures() which returns a list of
    IValue/ICategory objects. The underlying INode is accessed via .Node.
    """
    mapping: dict[str, str] = {}
    try:
        root = node_map.GetNode("Root")       # returns ICategory
        for feature in root.GetFeatures():    # direct children of Root
            node = feature.Node               # underlying INode
            if node.GetPrincipalInterfaceType() == genicam.intfICategory:
                cat_obj = node_map.GetNode(node.Name)   # get as ICategory
                top_display = node.DisplayName
                _fill_map(cat_obj, top_display, mapping, node_map)
    except Exception as e:
        pass
    return mapping


def _fill_map(cat_obj, top_category: str, mapping: dict, node_map, depth: int = 0):
    """Recursively assign top_category to every leaf node under this ICategory."""
    try:
        for feature in cat_obj.GetFeatures():
            node = feature.Node
            if not genicam.IsAvailable(node):
                continue
            if node.GetPrincipalInterfaceType() == genicam.intfICategory and depth < 8:
                child_cat = node_map.GetNode(node.Name)
                _fill_map(child_cat, top_category, mapping, node_map, depth + 1)
            else:
                mapping[node.Name] = top_category
    except Exception:
        pass


def get_category_for_node(node_name: str, mapping: dict) -> str:
    """Look up a node's top-level category from the pre-built map."""
    return mapping.get(node_name, "General")


# ---------------------------------------------------------------------------
# Camera scanning
# ---------------------------------------------------------------------------

def scan_camera(capture_only: bool = False) -> tuple[dict, list[dict]]:
    """Connect to the first Basler camera and return (camera_info, nodes).

    Args:
        capture_only: If True, only return nodes belonging to image/capture
                      categories (gain, exposure, format, white balance, etc.).
    """
    print("Connecting to Basler camera...")

    tl_factory = pylon.TlFactory.GetInstance()
    devices = tl_factory.EnumerateDevices()

    if not devices:
        raise RuntimeError("No Basler camera found. Make sure the camera is connected.")

    camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
    camera.Open()

    device_info = camera.GetDeviceInfo()
    camera_info = {
        "ModelName": device_info.GetModelName(),
        "SerialNumber": device_info.GetSerialNumber(),
        "DeviceVersion": device_info.GetDeviceVersion(),
        "DeviceClass": device_info.GetDeviceClass(),
    }

    print(f"Connected: {camera_info['ModelName']} (S/N: {camera_info['SerialNumber']})")
    print("Scanning node map — this may take a moment...")

    node_map = camera.GetNodeMap()
    all_nodes = node_map.GetNodes()

    # Build the category map once up front — much faster than per-node tree walks
    print("Building category map...")
    category_map = build_category_map(node_map)

    accessible_nodes = []
    skipped = 0

    for node_ref in all_nodes:
        raw_node = node_ref.GetNode()
        node_type = raw_node.GetPrincipalInterfaceType()

        if node_type not in (
            genicam.intfIEnumeration,
            genicam.intfIInteger,
            genicam.intfIFloat,
            genicam.intfIBoolean,
            genicam.intfIString,
            genicam.intfICommand,
        ):
            skipped += 1
            continue

        try:
            typed_node = node_map.GetNode(raw_node.Name)
        except Exception:
            skipped += 1
            continue

        info = get_node_info(typed_node)
        if info is None:
            skipped += 1
            continue

        info["category"] = get_category_for_node(raw_node.Name, category_map)

        # Skip nodes outside capture-relevant categories when filtering
        if capture_only and info["category"] not in CAPTURE_CATEGORIES:
            skipped += 1
            continue

        accessible_nodes.append(info)

    camera.Close()

    rw = sum(1 for n in accessible_nodes if n["access"] == "ReadWrite")
    ro = len(accessible_nodes) - rw
    filter_note = " (capture-only filter applied)" if capture_only else ""
    print(f"\nFound {len(accessible_nodes)} accessible nodes{filter_note}:")
    print(f"  Read/Write : {rw}")
    print(f"  Read Only  : {ro}")
    print(f"  Skipped    : {skipped}")

    return camera_info, accessible_nodes


def debug_tree() -> None:
    """Print all categories and their nodes using ICategory.GetFeatures()."""
    print("Connecting to Basler camera...")
    tl_factory = pylon.TlFactory.GetInstance()
    devices = tl_factory.EnumerateDevices()
    if not devices:
        raise RuntimeError("No Basler camera found.")

    camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
    camera.Open()
    device_info = camera.GetDeviceInfo()
    print(f"Connected: {device_info.GetModelName()} (S/N: {device_info.GetSerialNumber()})\n")

    node_map = camera.GetNodeMap()
    TYPE_LABELS = {
        genicam.intfIInteger:     "Int",
        genicam.intfIFloat:       "Float",
        genicam.intfIEnumeration: "Enum",
        genicam.intfIBoolean:     "Bool",
        genicam.intfIString:      "Str",
        genicam.intfICommand:     "Cmd",
        genicam.intfICategory:    "CAT",
    }

    def _print_cat(cat_obj, indent: int = 0):
        prefix = "  " * indent
        try:
            for feature in cat_obj.GetFeatures():
                node = feature.Node
                ntype = node.GetPrincipalInterfaceType()
                label = TYPE_LABELS.get(ntype, "?")
                avail = "✓" if genicam.IsAvailable(node) else "✗"
                print(f"{prefix}[{label}] {node.Name!r}  ({node.DisplayName})  {avail}")
                if ntype == genicam.intfICategory and indent < 4:
                    child_cat = node_map.GetNode(node.Name)
                    _print_cat(child_cat, indent + 1)
        except Exception as e:
            print(f"{prefix}[ERR] {e}")

    print("=== GenICam Node Tree ===\n")
    try:
        root = node_map.GetNode("Root")
        _print_cat(root)
    except Exception as e:
        print(f"ERROR: {e}")

    camera.Close()


def list_categories() -> None:
    """Connect to the camera, print every category name found, then exit.

    Use this to discover the exact category names your camera uses so you
    can verify (or extend) CAPTURE_CATEGORIES if --capture-only returns nothing.
    """
    print("Connecting to Basler camera...")
    tl_factory = pylon.TlFactory.GetInstance()
    devices = tl_factory.EnumerateDevices()
    if not devices:
        raise RuntimeError("No Basler camera found.")

    camera = pylon.InstantCamera(tl_factory.CreateFirstDevice())
    camera.Open()
    device_info = camera.GetDeviceInfo()
    print(f"Connected: {device_info.GetModelName()} (S/N: {device_info.GetSerialNumber()})\n")

    node_map = camera.GetNodeMap()
    all_nodes = node_map.GetNodes()

    category_map = build_category_map(node_map)

    # Count how many nodes fall into each category
    seen: dict[str, int] = {}
    for node_ref in all_nodes:
        raw_node = node_ref.GetNode()
        if _is_category(raw_node):
            continue
        if not _node_is_available(raw_node):
            continue
        cat = get_category_for_node(_node_name(raw_node), category_map)
        seen[cat] = seen.get(cat, 0) + 1

    camera.Close()

    print("Categories found on this camera:")
    print(f"  {'Category name':<45}  Nodes")
    print(f"  {'-'*45}  -----")
    for cat, count in sorted(seen.items()):
        marker = "  <-- matched" if cat in CAPTURE_CATEGORIES else ""
        print(f"  {cat:<45}  {count:>5}{marker}")

    matched = sum(1 for c in seen if c in CAPTURE_CATEGORIES)
    print(f"\n{matched}/{len(seen)} categories matched by current CAPTURE_CATEGORIES.")
    if matched == 0:
        print("\n*** None matched — copy the relevant names above into CAPTURE_CATEGORIES ***")
    elif matched < len(seen):
        print("\nUnmatched categories (add to CAPTURE_CATEGORIES if needed):")
        for cat in sorted(seen):
            if cat not in CAPTURE_CATEGORIES:
                print(f"  \"{cat}\",")


# ---------------------------------------------------------------------------
# XML output
# ---------------------------------------------------------------------------

def write_xml(camera_info: dict, nodes: list[dict], output_file: str):
    root = ET.Element("BaslerCameraFeatures")

    cam_el = ET.SubElement(root, "CameraInfo")
    for k, v in camera_info.items():
        ET.SubElement(cam_el, k).text = str(v)

    categories: dict = {}
    for node in nodes:
        categories.setdefault(node["category"], []).append(node)

    features_el = ET.SubElement(root, "Features", attrib={"total": str(len(nodes))})

    for cat_name, items in sorted(categories.items()):
        cat_el = ET.SubElement(features_el, "Category",
                               attrib={"name": cat_name, "count": str(len(items))})
        for info in items:
            node_el = ET.SubElement(cat_el, "Node", attrib={
                "name": info["name"],
                "type": info["type"],
                "access": info["access"],
            })
            ET.SubElement(node_el, "DisplayName").text = info["display_name"]
            ET.SubElement(node_el, "Description").text = info["description"]
            ET.SubElement(node_el, "CurrentValue").text = info["current_value"]

            if info["type"] in ("Integer", "Float"):
                range_el = ET.SubElement(node_el, "Range")
                ET.SubElement(range_el, "Min").text = info["min"]
                ET.SubElement(range_el, "Max").text = info["max"]
                if info["type"] == "Integer" and info["increment"]:
                    ET.SubElement(range_el, "Increment").text = info["increment"]
                if info["type"] == "Float" and info["unit"] is not None:
                    ET.SubElement(range_el, "Unit").text = info["unit"]

            if info["options"]:
                opts_el = ET.SubElement(node_el, "Options")
                for opt in info["options"]:
                    ET.SubElement(opts_el, "Option").text = opt

            if info.get("pypylon_api"):
                api_el = ET.SubElement(node_el, "PylonAPI")
                for k, v in info["pypylon_api"].items():
                    ET.SubElement(api_el, k.capitalize()).text = str(v)

    raw = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(pretty)

    print(f"XML saved to: {output_file}")


# ---------------------------------------------------------------------------
# YAML output  (hand-built so we can embed inline comments)
# ---------------------------------------------------------------------------

def _yaml_str(value: str) -> str:
    """Quote a YAML string value if it contains special characters."""
    if value is None:
        return "null"
    specials = (":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|",
                 "-", "<", ">", "=", "!", "%", "@", "`", "'", '"', "\n")
    needs_quote = (
        any(c in value for c in specials)
        or value == ""
        or value.lower() in ("true", "false", "null")
    )
    if needs_quote:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return value


def _build_comment(info: dict) -> str:
    """Build a multi-line comment block above a YAML node entry."""
    indent = "  "
    lines = []

    lines.append(f"{indent}# -- {info['name']} --")

    if info["display_name"] and info["display_name"] != info["name"]:
        lines.append(f"{indent}# Display Name : {info['display_name']}")

    lines.append(f"{indent}# Type         : {info['type']}")
    lines.append(f"{indent}# Access       : {info['access']}")

    if info["type"] in ("Integer", "Float") and info["min"] is not None:
        range_str = f"{info['min']} .. {info['max']}"
        if info["type"] == "Integer" and info["increment"]:
            range_str += f"  (step: {info['increment']})"
        if info["type"] == "Float" and info["unit"]:
            range_str += f"  [{info['unit']}]"
        lines.append(f"{indent}# Range        : {range_str}")

    if info["options"]:
        # Wrap long option lists across multiple comment lines (max ~80 chars)
        opts = info["options"]
        prefix = f"{indent}# Options      : "
        line_buf = prefix
        for i, opt in enumerate(opts):
            chunk = opt + (", " if i < len(opts) - 1 else "")
            if len(line_buf) + len(chunk) > 88 and line_buf != prefix:
                lines.append(line_buf.rstrip(", "))
                line_buf = f"{indent}#               " + chunk
            else:
                line_buf += chunk
        lines.append(line_buf)

    if info["description"]:
        desc = info["description"].replace("\n", " ")
        # Wrap description at ~72 chars per comment line
        desc_prefix = f"{indent}# Description : "
        cont_prefix = f"{indent}#               "
        words = desc.split()
        line_buf = desc_prefix
        for word in words:
            if len(line_buf) + len(word) + 1 > 88 and line_buf != desc_prefix:
                lines.append(line_buf.rstrip())
                line_buf = cont_prefix + word + " "
            else:
                line_buf += word + " "
        lines.append(line_buf.rstrip())

    if info.get("pypylon_api"):
        api = info["pypylon_api"]
        lines.append(f"{indent}# pypylon API  :")
        for k, v in api.items():
            lines.append(f"{indent}#   {k:<10}: {v}")

    return "\n".join(lines)


def write_yaml(camera_info: dict, nodes: list[dict], output_file: str):
    lines = []

    # File header
    lines.append("# =============================================================")
    lines.append("# Basler Camera Feature Export")
    lines.append("# Generated by basler_export_nodes.py")
    lines.append("# =============================================================")
    lines.append("#")
    lines.append("# Each parameter shows its current value as a plain YAML value.")
    lines.append("# The comment block above each entry describes:")
    lines.append("#   Type / Access / Range (min..max, step) / Options / Description")
    lines.append("#")
    lines.append("# To use this file in your application, load it with PyYAML:")
    lines.append("#   import yaml")
    lines.append("#   config = yaml.safe_load(open('basler_camera_nodes.yaml'))")
    lines.append("#   exposure = config['features']['AcquisitionControl']['ExposureTime']")
    lines.append("")

    # Camera info block
    lines.append("camera_info:")
    for k, v in camera_info.items():
        lines.append(f"  {k}: {_yaml_str(str(v))}")
    lines.append("")

    # Group by category
    categories: dict = {}
    for node in nodes:
        categories.setdefault(node["category"], []).append(node)

    lines.append("features:")
    lines.append("")

    for cat_name, items in sorted(categories.items()):
        safe_cat = cat_name.replace(" ", "_").replace("/", "_")
        lines.append(f"  # {'=' * 58}")
        lines.append(f"  # {cat_name}  ({len(items)} nodes)")
        lines.append(f"  # {'=' * 58}")
        lines.append(f"  {safe_cat}:")
        lines.append("")

        for info in items:
            # Multi-line comment block
            lines.append(_build_comment(info))
            # The actual value line
            value = _yaml_str(str(info["current_value"])) if info["current_value"] is not None else "null"
            lines.append(f"    {info['name']}: {value}")
            lines.append("")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"YAML saved to: {output_file}")


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def write_markdown(camera_info: dict, nodes: list[dict], output_file: str):
    lines = []
    rw  = sum(1 for n in nodes if n["access"] == "ReadWrite")
    ro  = len(nodes) - rw

    # ── Title & camera info ──────────────────────────────────────────────────
    lines += [
        f"# Basler Camera Feature Reference",
        f"",
        f"| Property | Value |",
        f"|---|---|",
        f"| Model | `{camera_info['ModelName']}` |",
        f"| Serial Number | `{camera_info['SerialNumber']}` |",
        f"| Device Version | `{camera_info['DeviceVersion']}` |",
        f"| Device Class | `{camera_info['DeviceClass']}` |",
        f"| Total Parameters | {len(nodes)} ({rw} read/write, {ro} read-only) |",
        f"",
    ]

    # ── Table of contents ────────────────────────────────────────────────────
    categories: dict = {}
    for node in nodes:
        categories.setdefault(node["category"], []).append(node)

    lines += ["## Table of Contents", ""]
    for cat_name in sorted(categories):
        anchor = cat_name.lower().replace(" ", "-").replace("/", "").replace("(", "").replace(")", "")
        count  = len(categories[cat_name])
        lines.append(f"- [{cat_name}](#{anchor}) — {count} parameters")
    lines.append("")

    # ── Per-category sections ────────────────────────────────────────────────
    ACCESS_BADGE = {
        "ReadWrite": "![ReadWrite](https://img.shields.io/badge/access-ReadWrite-green)",
        "ReadOnly":  "![ReadOnly](https://img.shields.io/badge/access-ReadOnly-lightgrey)",
    }
    TYPE_BADGE = {
        "Float":       "![Float](https://img.shields.io/badge/type-Float-blue)",
        "Integer":     "![Integer](https://img.shields.io/badge/type-Integer-blue)",
        "Enumeration": "![Enum](https://img.shields.io/badge/type-Enum-purple)",
        "Boolean":     "![Boolean](https://img.shields.io/badge/type-Boolean-orange)",
        "String":      "![String](https://img.shields.io/badge/type-String-yellow)",
        "Command":     "![Command](https://img.shields.io/badge/type-Command-red)",
    }

    for cat_name, items in sorted(categories.items()):
        lines += [f"---", f"", f"## {cat_name}", f""]

        for info in items:
            name         = info["name"]
            display_name = info["display_name"]
            ntype        = info["type"]
            access       = info["access"]
            description  = info["description"] or "_No description available._"
            current      = info["current_value"]
            api          = info.get("pypylon_api", {})

            type_badge   = TYPE_BADGE.get(ntype, f"`{ntype}`")
            access_badge = ACCESS_BADGE.get(access, f"`{access}`")

            # Parameter heading
            lines += [
                f"### `{name}`",
                f"",
                f"**{display_name}** &nbsp; {type_badge} &nbsp; {access_badge}",
                f"",
                f"{description}",
                f"",
            ]

            # Details table
            table_rows = [("Current value", f"`{current}`")]

            if ntype in ("Integer", "Float") and info["min"] is not None:
                range_str = f"`{info['min']}` → `{info['max']}`"
                if ntype == "Integer" and info["increment"]:
                    range_str += f" (step `{info['increment']}`)"
                if ntype == "Float" and info["unit"]:
                    range_str += f" {info['unit']}"
                table_rows.append(("Range", range_str))

            if info["options"]:
                opts_md = " ".join(f"`{o}`" for o in info["options"])
                table_rows.append(("Options", opts_md))

            lines += ["| Property | Value |", "|---|---|"]
            for k, v in table_rows:
                lines.append(f"| {k} | {v} |")
            lines.append("")

            # pypylon API code block
            if api:
                lines += ["**pypylon API**", ""]
                if ntype == "Command":
                    lines += [
                        "```python",
                        f"camera.{name}.Execute()",
                        "```",
                    ]
                elif ntype == "Enumeration" and info["options"]:
                    lines += [
                        "```python",
                        f"# Get",
                        f"value = camera.{name}.Value",
                        f"",
                        f"# Set (choose one option)",
                    ]
                    for opt in info["options"]:
                        lines.append(f'camera.{name}.Value = "{opt}"')
                    lines.append("```")
                elif ntype == "Boolean":
                    lines += [
                        "```python",
                        f"# Get",
                        f"value = camera.{name}.Value",
                        f"",
                        f"# Set",
                        f"camera.{name}.Value = True   # or False",
                        "```",
                    ]
                else:
                    lines += [
                        "```python",
                        f"# Get",
                        f"value = camera.{name}.Value",
                        f"",
                        f"# Set",
                        f"camera.{name}.Value = <value>",
                        "```",
                    ]
                lines.append("")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Markdown saved to: {output_file}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export all readable/writable Basler camera nodes to XML or YAML."
    )
    parser.add_argument(
        "--debug-tree", "-d",
        action="store_true",
        default=False,
        help=(
            "Print the raw GenICam category tree from the camera. Use this when "
            "--list-categories shows everything as 'General' to see the actual "
            "node tree structure and find the correct category names."
        ),
    )
    parser.add_argument(
        "--list-categories", "-l",
        action="store_true",
        default=False,
        help=(
            "Print all category names found on the connected camera, noting which "
            "are already matched by CAPTURE_CATEGORIES. Use this to diagnose an "
            "empty --capture-only result."
        ),
    )
    parser.add_argument(
        "--format", "-f",
        choices=["xml", "yaml", "markdown"],
        default="xml",
        help="Output format: 'xml' (default), 'yaml', or 'markdown'",
    )
    parser.add_argument(
        "--capture-only", "-c",
        action="store_true",
        default=False,
        help=(
            "Only export image/capture-relevant settings: acquisition control, "
            "analog control (gain/gamma), image format, white balance, colour "
            "transformation, and auto-function controls. Excludes transport, "
            "device info, I/O, file access, and other non-capture categories."
        ),
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path. Defaults to 'basler_camera_nodes.xml' or '.yaml'",
    )
    args = parser.parse_args()

    # Diagnostic modes — print info and exit
    if args.debug_tree:
        debug_tree()
        return

    if args.list_categories:
        list_categories()
        return

    if args.output is None:
        ext = "md" if args.format == "markdown" else args.format
        args.output = f"basler_camera_nodes.{ext}"

    camera_info, nodes = scan_camera(capture_only=args.capture_only)

    if args.format == "xml":
        write_xml(camera_info, nodes, args.output)
    elif args.format == "yaml":
        write_yaml(camera_info, nodes, args.output)
    else:
        write_markdown(camera_info, nodes, args.output)


if __name__ == "__main__":
    main()
