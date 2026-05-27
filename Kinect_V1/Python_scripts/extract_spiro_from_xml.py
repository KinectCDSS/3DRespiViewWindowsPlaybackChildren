import xml.etree.ElementTree as ET
import pandas as pd
import os

#Sur easyoneConnect, Utilitaires, exportation XML

# Fonction pour parser le fichier XML et extraire les données
def parse_xml(file_path):
    # Charger et analyser le fichier XML
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Liste pour stocker les résultats de chaque channel
    patient_data = []

    # Parcours des balises <Patient>
    for patient in root.findall(".//Patient"):
        patient_id = patient.get('ID')  # Récupérer l'ID du patient
        
        # Parcours de chaque <ChannelVolume> du patient
        for idx, channel in enumerate(patient.findall(".//ChannelVolume")):
            sampling_values = channel.find('.//SamplingValues').text.strip().split()  # Récupérer les valeurs de sampling
            
            # Convertir les valeurs de sampling en float et les multiplier par 1000
            sampling_values = [float(value) * 1000 for value in sampling_values]
            
            # Ajouter les données dans la liste
            patient_data.append({
                'PatientID': patient_id,
                'ChannelData': sampling_values,
                'ChannelIndex': idx + 1  # Ajouter un index pour incrémenter les noms de fichiers
            })

    return patient_data

# Fonction pour enregistrer les données dans un fichier CSV
def save_to_csv(data, output_dir):
    for entry in data:
        patient_id = entry['PatientID']
        channel_data = entry['ChannelData']
        channel_index = entry['ChannelIndex']
        
        # Créer un nom de fichier basé sur l'ID du patient et l'index du channel
        file_name = f"{patient_id}_essai_{channel_index}.csv"
        file_path = os.path.join(output_dir, file_name)
        
        # Créer un DataFrame avec une seule colonne pour les valeurs de sampling
        df = pd.DataFrame(channel_data)
        
        # Enregistrer le DataFrame dans un fichier CSV sans header
        df.to_csv(file_path, index=False, header=False)

# Fonction principale
def main():
    # Définir le chemin du fichier XML
    xml_file_path = "C://Users//flori//Downloads//test.xml"
    output_directory = "C://Users//flori//Downloads//"

    # Créer le dossier de sortie si il n'existe pas
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Extraire les données du fichier XML
    patient_data = parse_xml(xml_file_path)

    # Sauvegarder les données extraites dans des fichiers CSV
    save_to_csv(patient_data, output_directory)

if __name__ == "__main__":
    main()
