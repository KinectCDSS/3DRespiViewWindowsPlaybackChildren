import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, firwin, filtfilt
import pandas as pd
from matplotlib.widgets import CheckButtons

# Paramètres du filtre
filter_order = 12  # Ordre du filtre FIR
relative_safe_margin = 0.0
max_respiratory_rate_bpm = 50  # Resp/min
frequency_cutoff_hz = max_respiratory_rate_bpm * (1 + relative_safe_margin) / 60  # Hz avec marge
sampling_rate_kinect_hz = 30  # Taux d'échantillonnage des données Kinect (à ajuster si nécessaire)

# Fonction pour supprimer les valeurs aberrantes
def remove_outliers(data):
    if len(data) < 4:  # Pas assez de données pour détecter des valeurs aberrantes
        return data
    q1 = np.percentile(data, 25)
    q3 = np.percentile(data, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    for i in range(len(data)):
        if data[i] < lower_bound or data[i] > upper_bound:
            if i == 0:
                data[i] = data[i+1]
            elif i == len(data) - 1:
                data[i] = data[i-1]
            else:
                data[i] = (data[i-1] + data[i+1]) / 2
    return data

def update_display():
    ax2.clear()  # Efface le graphique actuel
    ax2.set_title('Constante respiratoire')
    ax2.axis('off')
    
    # Compter le nombre de cases à cocher qui sont activées
    active_status = [show_volume.get_status()[0], show_ti.get_status()[0], show_te.get_status()[0]]
    num_active = sum(active_status)

    # Définir les positions x selon le nombre de cases activées
    if num_active == 0:
        x_positions = [0.5]  # Centrer tout le texte si aucune case n'est activée
    elif num_active == 1:
        x_positions = [0.3, 0.8] 
    elif num_active == 2:
        x_positions = [0.2, 0.6, 0.8]
    else:
        x_positions = [0.2, 0.5, 0.7, 0.9]

    # Affichage du titre et des informations principales
    ax2.text(x_positions[0], 0.8, f'Fréquence respiratoire: {round(FR)} Rpm', fontsize=15, ha='center')
    ax2.text(x_positions[0], 0.65, f'Volume minute expiré: {round(volume_minute/1000,2)} L/min', fontsize=15, ha='center')
    #Afficher volume moyen
    volume_moyen = np.mean(volume)
    ax2.text(x_positions[0], 0.5, f'Volume courant moyen: {round(volume_moyen)} mL', fontsize=15, ha='center')
    ax2.text(x_positions[0], 0.35, f'Temps moyen inspiration: {round(inspiration_time_mean, 1)} s', fontsize=15, ha='center')
    ax2.text(x_positions[0], 0.2, f'Temps moyen expiration: {round(expiration_time_mean, 1)} s', fontsize=15, ha='center')
    ax2.text(x_positions[0], 0.05, f'Rapport I/E: 1/{round(expiration_time_mean/inspiration_time_mean, 1)}', fontsize=15, ha='center')
    if len(peak_flow) > 0:
        ax2.text(x_positions[0], -0.1, f'Débit de pointe moyen: {round(peak_flow_mean)} mL/s', fontsize=15, ha='center')
    if len(troughs_flow) > 0:
        ax2.text(x_positions[0], -0.15, f'Débit de creux moyen: {round(troughs_flow_mean)} mL/s', fontsize=15, ha='center')


    index = 1  # Commencer à partir de la deuxième position dans x_positions pour le volume
    
    # Affichage des informations par cycle en fonction des cases à cocher sélectionnées
    if show_volume.get_status()[0]:
        for i in range(len(volume)):
            ax2.text(x_positions[index], 0.9 - 0.1 * (i + 1), f'Vc {i + 1}: {round(volume[i])} mL', fontsize=12, ha='center')
        index += 1  # Incrémenter l'index pour passer à la prochaine position
    if show_ti.get_status()[0]:
        for i in range(len(inspiration_time)):
            ax2.text(x_positions[index], 0.9 - 0.1 * (i+1), f'Ti {i + 1}: {round(inspiration_time[i], 2)} s', fontsize=12, ha='center')
        index += 1  # Incrémenter l'index
    if show_te.get_status()[0]:
        for i in range(len(expiration_time)):
            ax2.text(x_positions[index], 0.9 - 0.1 * (i+1), f'Te {i + 1}: {round(expiration_time[i], 2)} s', fontsize=12, ha='center')

    fig.canvas.draw()  # Redessine le graphique



# Conception du filtre passe-bas FIR
filter_fir = firwin(numtaps=filter_order + 1, cutoff=frequency_cutoff_hz, fs=sampling_rate_kinect_hz)


# Variables pour tracer les données brutes en temps réel

# Création de la figure avec 2 lignes: la première pour les données brutes (largeur complète), et la deuxième pour les deux autres graphiques
fig = plt.figure(figsize=(18, 12))  # Taille ajustée pour mieux répartir les sous-graphiques
# Premier graphique: Données brutes et filtrées (pleine largeur)
ax1 = plt.subplot2grid((3, 2), (0, 0), colspan=2)  # Occupant toute la largeur en haut

ax2 = plt.subplot2grid((3, 2), (1, 0))

# Quatrième graphique: Nouveau graphique supplémentaire qui occupe toute la largeur en bas
ax4 = plt.subplot2grid((3, 2), (2, 0), colspan=2)  # Occupant toute la largeur en bas

freq_ax = ax2
freq_ax.set_title('Constante respiratoire')
freq_ax.axis('off')

# --- Quatrième graphique: Courbe débit - temps
ax4.set_xlim(0, 30)
ax4.set_xlabel('Temps (s)')
ax4.set_ylim(-2000, 2000)
ax4.set_ylabel('Amplitude en mL')
ax4.grid()
ax4.set_title('Variation du débit en fonction du temps')
#Rend la ligne de la grille qui croise le zéro plus épaisse
ax4.axhline(y=0, color='slategray', linewidth=2)


x_data, y_data, y_filtered_data = np.array([]), np.array([]), np.array([])
line_raw, = ax1.plot([], [], label='Données brutes', color='b')
line_filtered, = ax1.plot([], [], label='Données filtrées', color='g')
scatter_peaks = ax1.scatter([], [], color='r', label='Pics', marker='x')
scatter_troughs = ax1.scatter([], [], color='y', label='Creux', marker='o')
scatter_peaks_derivative = ax4.scatter([], [], color='r', label='Pics', marker='x')
scatter_troughs_derivative = ax4.scatter([], [], color='y', label='Creux', marker='o')
line_derivative, = ax4.plot([], [], label='Flow', color='b')

# Configuration des axes
ax1.set_xlim(0, 30)
ax1.set_ylim(-2000, 2000)
ax1.set_xlabel('Temps (s)')
ax1.set_ylabel('Amplitude en mL')
ax1.grid()
ax1.legend()
ax1.set_title('Variation du volume en fonction du temps')
manager = plt.get_current_fig_manager()
manager.full_screen_toggle()


# Lire les données à partir d'un fichier CSV
# Remplacez 'data.csv' par le chemin de votre fichier CSV
input_file = "E:\\SIspiro\\15_essai_6.csv"
dataframe = pd.read_csv(input_file)


# Demander à l'utilisateur à partir de combien de secondes commencer à lire les données
start_seconds = float(input("À partir de combien de secondes voulez-vous commencer ? "))
start_index = int(start_seconds * 100)  # Calculer l'index de départ en multipliant par 100
# Demander à l'utilisateur à partir de combien de secondes arrêter de lire les données
end_seconds = float(input("À combien de secondes voulez-vous arrêter ? "))
end_index = int(end_seconds * 100)  # Calculer l'index de fin en multipliant par 100

#Les valeurs sont dans la première colonne
data_values = dataframe.iloc[start_index:end_index, 0].values

# Variables de contrôle
scale = data_values[0]

# Lecture et traitement des données en temps réel
for index, y_value in enumerate(data_values):  
    y_data=np.append(y_data,y_value - scale)
    x_data=np.append(x_data,index / 100)  # Index divisé par le taux d'échantillonnage

# Supprimer les valeurs aberrantes
y_data_cleaned = remove_outliers(y_data)

# Appliquer le filtre FIR si assez de données sont présentes
if len(y_data_cleaned) > filter_order * 5:
    y_filtered_data = filtfilt(filter_fir, 1.0, y_data_cleaned)

# Mettre à jour les données de la ligne brute
line_raw.set_data(x_data, y_data)

# Mettre à jour les données filtrées
if len(y_filtered_data) > 0:
    line_filtered.set_data(x_data[-len(y_filtered_data):], y_filtered_data)

    # Détecter les pics et creux dans les données filtrées
    y_filtered_array = np.array(y_filtered_data)
    peaks, _ = find_peaks(y_filtered_data, distance=130, width=50)
    troughs, _ = find_peaks(-y_filtered_data, distance=130, width=50)

    # Mettre à jour les coordonnées des pics et des creux
    scatter_peaks.set_offsets(np.c_[np.array(x_data)[peaks], y_filtered_data[peaks]])
    scatter_troughs.set_offsets(np.c_[np.array(x_data)[troughs], y_filtered_data[troughs]])

    dy_dx = np.gradient(y_filtered_data, x_data[:len(y_filtered_data)])
    line_derivative.set_data(x_data[:len(dy_dx)], dy_dx)

    FR_temp = (len(troughs) - 1) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])
    # Détecter les pics et creux sur la dérivée
    peaks_derivative, _ = find_peaks(dy_dx, height=100, distance=int(30 * 100 / FR_temp))
    troughs_derivative, _ = find_peaks(-dy_dx, height=100, distance=int(30 * 100 / FR_temp))

    # Mettre à jour les coordonnées des pics et des creux sur la dérivée
    scatter_peaks_derivative.set_offsets(np.c_[np.array(x_data)[peaks_derivative], dy_dx[peaks_derivative]])
    scatter_troughs_derivative.set_offsets(np.c_[np.array(x_data)[troughs_derivative], dy_dx[troughs_derivative]])
    # Le débit de pointe vaut la valeur de la dérivée aux pics
    peak_flow = dy_dx[peaks_derivative]
    troughs_flow = -dy_dx[troughs_derivative]
    # Calculer la moyenne des pics de débit
    if len(peak_flow) > 0:
        peak_flow_mean = np.mean(peak_flow)
    if len(troughs_flow) > 0:
        troughs_flow_mean = np.mean(troughs_flow)


    
# Il faut débuter par une expiration et finir par une expiration
print(len(peaks))
print(len(troughs))


# --- Calculs de la fréquence respiratoire et des volumes ---
if peaks[0] < troughs[0]:
    peaks = peaks[1:]
if peaks[-1] > troughs[-1]:
    peaks = peaks[:-1]

if len(peaks)+1== len(troughs):
    FR = (len(troughs) - 1) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])

    volume = []
    inspiration_time=[]
    expiration_time=[]
    for i in range(2, len(troughs) + 1, 1):
        volume.append(y_filtered_data[peaks[i - 2]] - y_filtered_data[troughs[i - 1]])
        inspiration_time.append(x_data[peaks[i - 2]] - x_data[troughs[i - 2]])
        expiration_time.append(x_data[troughs[i - 1]] - x_data[peaks[i - 2]])

    volume_minute = sum(volume) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])
    inspiration_time_mean = np.mean(inspiration_time)
    expiration_time_mean = np.mean(expiration_time)

    # --- Mise à jour du graphique 2 avec la fréquence respiratoire et volumes ---
    # Création des cases à cocher
    ax_checkbox_volume = plt.axes([0.5, 0.55, 0.05, 0.025])  # Position de la case à cocher pour le volume
    show_volume = CheckButtons(ax_checkbox_volume, ['Vc par cycle'], [False])

    ax_checkbox_ti = plt.axes([0.5, 0.5, 0.05, 0.025])  # Position de la case à cocher pour Ti
    show_ti = CheckButtons(ax_checkbox_ti, ['Ti par cycle'], [False])

    ax_checkbox_te = plt.axes([0.5, 0.45, 0.05, 0.025])  # Position de la case à cocher pour Te
    show_te = CheckButtons(ax_checkbox_te, ['Te par cycle'], [False])

    #Boxes pour quitter
    ax_quit = plt.axes([0.5, 0.4, 0.05, 0.025])
    quit_button = CheckButtons(ax_quit, ['QUITTER'], [False])

    # Mise à jour de l'affichage en fonction des cases sélectionnées
    show_volume.on_clicked(lambda label: update_display())
    show_ti.on_clicked(lambda label: update_display())
    show_te.on_clicked(lambda label: update_display())
    quit_button.on_clicked(lambda label: plt.close())
    update_display()


plt.show() 
