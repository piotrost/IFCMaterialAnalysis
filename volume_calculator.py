import ifcopenshell
import ifcopenshell.geom
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from OCC.Core.GProp import GProp_GProps
from collections import defaultdict


from collections import Counter
import csv

model = ifcopenshell.open('AC20-Institute-Var-2.ifc')

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


def get_spatial_location(element):
    rels = model.get_inverse(element)
    for rel in rels:
        if rel.is_a("IfcRelContainedInSpatialStructure"):
            location = rel.RelatingStructure
            return f"{location.is_a()} - {location.Name}"
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
    # Domyślnie przyjmujemy metry
    return 1.0


# Konfiguracja geometrii IFC
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

length_scale = get_length_unit_scale()
volume_scale = length_scale ** 3  # objętość = długość³



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




# Liczenie i eksport CSV
mat_list = []
with open("material_report.csv", mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["ElementType", "Name", "GlobalId", "Material", "Location", "Volume [m³]"])

    for element in elements:
        material = get_material_name(element)
        name = element.Name if element.Name else "Unnamed"
        location = get_spatial_location(element)

        volume = get_volume_from_quantities(element)
        if volume is None:
            volume = get_geometric_volume(element)

        volume_str = round(volume, 3) if volume else "N/A"
        writer.writerow([element.is_a(), name, element.GlobalId, material, location, volume_str])
        mat_list.append(material)

print("Zapisano plik: material_report.csv")

# Statystyki
counts = Counter(mat_list)
print("Podsumowanie materiałów:")
print(counts)


# Zbierz objętości wg (typ, materiał)
volume_by_type_material = defaultdict(float)

for element in elements:
    element_type = element.is_a()
    material = get_material_name(element)
    volume = get_volume_from_quantities(element)
    if volume is None:
        volume = get_geometric_volume(element)
    if volume:
        key = (element_type, material)
        volume_by_type_material[key] += volume * 1.0  # zabezpieczenie

# Zapisz do pliku CSV
with open("volume_summary_by_type_material.csv", mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["ElementType", "Material", "TotalVolume [m³]"])
    for (element_type, material), total_volume in volume_by_type_material.items():
        writer.writerow([element_type, material, round(total_volume, 3)])

print("Zapisano plik: volume_summary_by_type_material.csv")

