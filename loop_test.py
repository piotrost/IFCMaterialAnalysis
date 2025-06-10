import volume_calculator
import csv

if __name__ == "__main__":
    with open("output.csv", "a", newline="") as file:
        for i in range(100):
            print(f"Running iteration {i}")   
            result = volume_calculator.volume_calculator("AC20-Institute-Var-2.ifc", "key.json", "material_densities.json")
            csv.writer(file).writerow([result])