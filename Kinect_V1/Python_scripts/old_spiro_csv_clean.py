import csv
#Créer une liste vide pour stocker les valeurs
y_data = []

def update_csv_column(input_file):
    with open(input_file, mode='r') as file:
        csv_reader = csv.reader(file)
        #parcourir chaque ligne du fichier
        for row in csv_reader:
            #check if the row is not empty
            if row:
                #vérifie si la ligne contient "e" et si ou regarde la valeurs des chiffres derrère et le signe
                if 'e' in row[0]:
                    #split la ligne en deux partie
                    row_split = row[0].split('e')
                    print(row_split[1])
                    if row_split[1][0] == '+':
                        #prend la première partie et multiplie par 10 exposant row_split[1][2]
                        row[0] = float(row_split[0]) * (10 ** int(row_split[1][2]))
                    if row_split[1][0] == '-':
                        #prend la première partie et divise par 10
                        row[0] = float(row_split[0]) / (10 ** int(row_split[1][2]))
                    #Converti la valeur initialement en L en mL
                    row[0] = row[0] * 1000
                    #ajoute la valeur à la liste
                    y_data.append(row[0])
                    print(row[0])
   #Parcourir y_data et écrire chaque valeur dans une ligne du fichier
    with open(input_file, mode='w', newline='') as file:
        csv_writer = csv.writer(file)
        for value in y_data:
            csv_writer.writerow([value])
        print("Done")

# Exemple d'utilisation
input_file = 'C:\\Users\\flori\\OneDrive\\Bureau\\CHU_St_Justine\\005-Trial-1-15-5-51-699.csv'  # Chemin vers votre fichier CSV
update_csv_column(input_file)
