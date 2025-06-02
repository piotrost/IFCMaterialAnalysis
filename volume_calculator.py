import ifcopenshell
import ifcopenshell.geom
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from OCC.Core.GProp import GProp_GProps
from collections import defaultdict
import pandas as pd
from material_list import materials

model = ifcopenshell.open('AC20-Institute-Var-2.ifc')

types = ["IfcBeam", "IfcBearing", "IfcBuildingElementProxy", "IfcChimney", "IfcColumn", "IfcCovering",
         "IfcCurtainWall", "IfcDeepFoundation", "IfcDoor", "IfcFooting", "IfcMember", "IfcPlate",
         "IfcRailing", "IfcRamp", "IfcRampFlight", "IfcRoof", "IfcShadingDevice", "IfcSlab", "IfcStair",
         "IfcStairFlight", "IfcWall", "IfcWindow"]

valid_types = []
for t in types:
    try:
        model.by_type(t)
        valid_types.append(t)
    except RuntimeError:
        print(f"Typ {t} nie został znaleziony w IFC.")

elements = []
for t in valid_types:
    elements.extend(model.by_type(t))


def get_material_name(element):
    rels = model.get_inverse(element)
    for rel in rels:
        if rel.is_a("IfcRelAssociatesMaterial"):
            mat = rel.RelatingMaterial
            if mat.is_a("IfcMaterial"):
                return mat.Name
            elif mat.is_a("IfcMaterialLayerSetUsage"):
                layers = mat.ForLayerSet.MaterialLayers
                if layers:
                    return layers[0].Material.Name
            elif mat.is_a("IfcMaterialLayerSet"):
                layers = mat.MaterialLayers
                if layers:
                    return layers[0].Material.Name
            elif mat.is_a("IfcMaterialConstituentSet"):
                if mat.MaterialConstituents:
                    return mat.MaterialConstituents[0].Material.Name
    return "Unknown"


def get_volume_from_quantities(element):
    rels = model.get_inverse(element)
    for rel in rels:
        if rel.is_a("IfcRelDefinesByProperties"):
            prop_def = rel.RelatingPropertyDefinition
            if prop_def.is_a("IfcElementQuantity"):
                for qty in prop_def.Quantities:
                    if qty.is_a("IfcQuantityVolume"):
                        return qty.VolumeValue
    return None


def get_length_unit_scale():
    unit_assignments = model.by_type("IfcUnitAssignment")
    for ua in unit_assignments:
        for unit in ua.Units:
            if unit.is_a("IfcSIUnit") and unit.UnitType == "LENGTHUNIT":
                if unit.Name == "METRE":
                    return 1.0
                elif unit.Name == "MILLIMETRE":
                    return 0.001
                elif unit.Name == "CENTIMETRE":
                    return 0.01
                elif unit.Name == "INCH":
                    return 0.0254
    return 1.0


settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

length_scale = get_length_unit_scale()
volume_scale = length_scale ** 3



def get_geometric_volume(element):
    try:
        shape_items = list(ifcopenshell.geom.iterator(settings, model, [element]))
        if not shape_items:
            return None
        shape = shape_items[0]
        brep = shape.geometry
        props = GProp_GProps()
        brepgprop_VolumeProperties(brep, props)
        volume = props.Mass()
        return volume * volume_scale
    except Exception as e:
        print(f"Błąd geometrii dla elementu {element.GlobalId}: {e}")
        return None


volume_by_type_material = defaultdict(float)

for element in elements:
    element_type = element.is_a()
    material = get_material_name(element)
    volume = get_volume_from_quantities(element)
    if volume is None:
        volume = get_geometric_volume(element)
    if volume:
        key = (element_type, material)
        volume_by_type_material[key] += volume * 1.0

summary_data = []

for (element_type, material), total_volume in volume_by_type_material.items():
    summary_data.append({
        "Element": element_type,
        "Materiał bud.": material,
        "Objętość [m³]": round(total_volume, 3)
    })

summary_df = pd.DataFrame(summary_data)


def match_and_multiply(material_name, volume):
    for key, multiplier in materials.items():
        if key.lower() in material_name.lower():
            return round(volume * multiplier, 3)
    return None  # lub np. 0


summary_df["Masa [kg]"] = summary_df.apply(
    lambda row: match_and_multiply(row["Materiał bud."], row["Objętość [m³]"]), axis=1)
total_mass = summary_df["Masa [kg]"].sum()

print(summary_df)
print(f"Suma masy: {round(total_mass, 3)} kg")
