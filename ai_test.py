from openai import OpenAI

# Function to get density of a material in kg/m3 using OpenAI API
def get_material_density(key, material, temperature=0):
    # get OpenAI client
    client = OpenAI(api_key=key)
    
    prompt = f"Return density of material '{material}' in kg/m3 as integer. Do not include additional characters."

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
    

if __name__ == "__main__":
    import json
    import sys

    # get material
    material = sys.argv[1] if len(sys.argv) > 1 else "Wasser"

    # get api key from file
    with open('data/key.json', 'r', encoding='utf-8') as f:
        key_dict = json.load(f)
    key = key_dict['key']

    # Call the function to get density
    density = get_material_density(
        key,
        material,
        temperature=0
    )
    
    print(f"Density of {material}: {density} kg/m³")