import ifcopenshell
from collections import Counter

model = ifcopenshell.open('Budynek_usługowy_IFC4.ifc')

types = ["IfcBeam",
         "IfcBearing",
         "IfcBuildingElementProxy",
         "IfcChimney",
         "IfcColumn",
         "IfcCovering",
         "IfcCurtainWall",
         "IfcDeepFoundation",
         "IfcDoor",
         "IfcFooting",
         "IfcMember",
         "IfcPlate",
         "IfcRailing",
         "IfcRamp",
         "IfcRampFlight",
         "IfcRoof",
         "IfcShadingDevice",
         "IfcSlab",
         "IfcStair",
         "IfcStairFlight",
         "IfcWall",
         "IfcWindow"]

valid_types = []
for t in types:
    try:
        model.by_type(t)
        valid_types.append(t)
    except RuntimeError:
        print(f"Warning: Type {t} not found in schema.")

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


mat_list = []
for i in elements:
    mat_name = get_material_name(i)
    mat_list.append(mat_name)

print(mat_list)

counts = Counter(mat_list)
print(counts)
