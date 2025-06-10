# Authors: Remigiusz Szewczak, Maciej Mirowski, Piotr Ostaszewski

import ifcopenshell
import ifcopenshell.geom
from OCC.Core.BRepGProp import brepgprop_VolumeProperties
from OCC.Core.GProp import GProp_GProps
from collections import defaultdict
import pandas as pd
from openai import OpenAI
import regex
import json

# types of objects that might have volume
volume_object_types = [
    "IfcBeam", "IfcBearing", "IfcBuildingElementProxy", "IfcChimney", "IfcColumn", "IfcCovering",
    "IfcCurtainWall", "IfcDeepFoundation", "IfcDoor", "IfcFooting", "IfcMember", "IfcPlate",
    "IfcRailing", "IfcRamp", "IfcRampFlight", "IfcRoof", "IfcShadingDevice", "IfcSlab", "IfcStair",
    "IfcStairFlight", "IfcWall", "IfcWindow"
]

# get element's material name based on its relationships
def get_material_name(model, element):
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
        return "_unknown"

# get volume from element's related quantities
def get_volume_from_quantities(model, element):
    rels = model.get_inverse(element)
    for rel in rels:
        if rel.is_a("IfcRelDefinesByProperties"):
            prop_def = rel.RelatingPropertyDefinition
            if prop_def.is_a("IfcElementQuantity"):
                for qty in prop_def.Quantities:
                    if qty.is_a("IfcQuantityVolume"):
                        return qty.VolumeValue
    return None

# get length unit scale relative to meters
# quantity_in_model_units * model_length_unit_scale = quantity_in_meters
def get_length_unit_scale(model):
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

# Get geometric volume of an element based on its geometry
def get_geometric_volume(model, settings, volume_scale, element):
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
        print(f"Wrong geometry for element {element.GlobalId}: {e}")
        return None

# Function to get density of a material in kg/m3 using OpenAI API
def get_material_density(key, material, temperature=0):
    # get OpenAI client
    client = OpenAI(api_key=key)
    
    prompt = f"Return density of material '{material}' in kg/m3 as integer. Do not include additional characters. For invalid materials return 0."

    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=10  # keep output minimal
    )

    # Extract the number
    density_str = response.choices[0].message.content.strip()
    density = int(density_str)

    return density

# count the mass of material
def count_mass_of_material(full_material_name, volume, material_dict, openai_key):
    # remove non-letter characters
    short_name = regex.sub(r'[^\p{L}]', '', full_material_name.lower())
    
    # material already in dictionary
    if short_name in material_dict:
        # if material is in dictionary but has zero density, consider it invalid
        if material_dict[short_name] == 0:
            print(f"Material '{short_name}' considerd invalid, skipping.")
            return None
        return volume * material_dict[short_name]
    
    # unknown material
    elif full_material_name == "_unknown":
        return None
    
    # ask AI
    elif openai_key is not None:
        try:
            # get density from OpenAI API
            density = get_material_density(openai_key, short_name)
            # if density is zero, consider material invalid
            if density == 0:
                print(f"Material '{short_name}' considerd invalid by AI, skipping.")
            
            material_dict[short_name] = density
            return volume * density
        except Exception as e:
            print(f"Error getting density for material '{short_name}': {e}")            
        
    return None  # if trouble with OpenAI API

# ************************************************************************************************************

def volume_calculator(ifc_file, key_path, material_dict_path):    
    # Load OpenAI API key from JSON file
    try:
        key_dict = json.load(open(key_path, 'r'))
        openai_key = key_dict['key']
    except:
        print("OpenAI API key not found. Please provide a valid path to the key file.")
        openai_key = None
    
    
    # Load material densities dictionary from JSON file or create an empty one
    try:
        material_dict = json.load(open(material_dict_path, 'r'))
    except:
        material_dict = {}

    # ----------------------------------------------------------------------------
    
    # Load the IFC model
    model = ifcopenshell.open(ifc_file)
    if not model:
        raise ValueError("Failed to open IFC file. Please check the file path and format.")

    # filter object types by compatibility with file's schema vesrion
    valid_vol_obj_types = []
    for t in volume_object_types:
        try:
            model.by_type(t)
            valid_vol_obj_types.append(t)
        except RuntimeError:
            print(f"Type {t} not found in IFC.")

    # Collect all elements of valid types
    vol_obj_elements = []
    for t in valid_vol_obj_types:
        vol_obj_elements.extend(model.by_type(t))

    # -----------------------------------------------------------------------------

    # Set world coordinates for geometry processing
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    # Get the length unit scale and calculate volume scale
    length_scale = get_length_unit_scale(model)                     # quantity_in_model_units * model_length_unit_scale = quantity_in_meters
    volume_scale = length_scale ** 3

    # create dictionary to sum up volumes grouped by pair (element_type, material)
    volume_by_type_and_material = defaultdict(float)
    for element in vol_obj_elements:
        # get element type and material
        element_type = element.is_a()
        material = get_material_name(model, element)
        
        # get volume from element's related quantities or count geometric volume
        # volume = get_geometric_volume(model, settings, volume_scale, element)
        volume = get_volume_from_quantities(model, element)
        if volume is not None:
            volume *= volume_scale
        else:
            volume = get_geometric_volume(model, settings, volume_scale, element)
        
        # add volume if successfully retrieved
        if volume:
            key = (element_type, material)
            volume_by_type_and_material[key] += float(volume)

    # ----------------------------------------------------------------------------

    # create data frame for summary
    summary_data = []
    for (element_type, material), total_volume in volume_by_type_and_material.items():
        summary_data.append({
            "Element": element_type,
            "Material": material,
            "Volume [m³]": total_volume
        })
    summary_df = pd.DataFrame(summary_data)

    # count mass of each material in the model
    summary_df["Mass [kg]"] = summary_df.apply(
        lambda row: count_mass_of_material(row["Material"], row["Volume [m³]"], material_dict, openai_key),
        axis=1
    )
    
    total_mass = summary_df["Mass [kg]"].sum()

    # print results
    summary_df["Volume [m³]"] = summary_df["Volume [m³]"].round(3)
    summary_df["Mass [kg]"] = summary_df["Mass [kg]"].round(3)
    print(summary_df)

    # save material dictionary to JSON file
    with open(material_dict_path, 'w', encoding='utf-8') as f:
        json.dump(material_dict, f, indent=4)

    return total_mass



if __name__ == "__main__":
    import argparse
    
    # set up argument parser
    parser = argparse.ArgumentParser(description="Calculate volumes and masses of elements in an IFC file.")
    parser.add_argument("ifc_file", help="Path to the IFC file")
    parser.add_argument("--key", help="OpenAI API key for material density lookup", default="key.json")
    parser.add_argument("--material_dict", help="Path to the material density dictionary JSON file", default="material_densities.json")

    args = parser.parse_args()

    # run the volume calculator
    total_mass = volume_calculator(ifc_file=args.ifc_file, key_path=args.key, material_dict_path=args.material_dict)
    print(f"Whole mass: {round(total_mass, 3)} kg")
