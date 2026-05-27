import socket
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from scipy.signal import find_peaks, firwin, filtfilt
from matplotlib.widgets import CheckButtons


# Configuration du socket
host = '127.0.0.1'
port = 5000
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((host, port))
sock.listen(1)
conn, addr = sock.accept()

# Paramètres du filtre
filter_order = 12  # Ordre du filtre FIR
relative_safe_margin = 0.0
max_respiratory_rate_bpm = 50  # Resp/min
frequency_cutoff_hz = max_respiratory_rate_bpm * (1 + relative_safe_margin) / 60  # Hz avec marge
sampling_rate_kinect_hz = 30  # Taux d'échantillonnage des données Kinect (à ajuster si nécessaire)
    

def remove_outliers(data):
    # Calcul des différences entre les valeurs successives
    differences = np.diff(data)
    # Calcul de l'écart interquartile
    iqr = np.percentile(differences, 75) - np.percentile(differences, 25)
    # Calcul des limites supérieure et inférieure
    lower_bound = np.percentile(differences, 25) - 0.5*iqr
    upper_bound = np.percentile(differences, 75) + 0.5*iqr
    # Parcourir les différences et remplacer les valeurs aberrantes par la valeur précédente
    for i in range(1, len(differences)):
        if differences[i] < lower_bound or differences[i] > upper_bound:
            data[i + 1] = data[i]
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
    # Afficher le débit de pointe moyen
    ax2.text(x_positions[0], -0.1, f'Débit de pointe moyen: {round(peak_flow_mean)} mL/s', fontsize=15, ha='center')
    # Afficher le débit de creux moyen
    ax2.text(x_positions[0], -0.15, f'Débit de creux moyen: {round(trough_flow_mean)} mL/s', fontsize=15, ha='center')

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

# --- Premier graphique: Données brutes et filtrées ---
#Make x_data and y_data numpy arrays
x_data = np.array([])
y_data = np.array([])
y_filtered = np.array([])

# Lecture et traitement des données en temps réel
flag = True
flagScale = True
scale = 0

# Création de la figure avec 3 lignes: la première pour les données brutes (largeur complète),
# la deuxième pour les deux autres graphiques, et la troisième pour le graphique supplémentaire.
fig = plt.figure(figsize=(18, 12))  # Taille ajustée pour mieux répartir les sous-graphique

# Premier graphique: Données brutes et filtrées (pleine largeur)
ax1 = plt.subplot2grid((3, 2), (0, 0), colspan=2)  # Occupant toute la largeur en haut

# Deuxième graphique: Fréquence respiratoire (en bas à gauche, occupant deux colonnes)
ax2 = plt.subplot2grid((3, 2), (1, 0))

# Troisième graphique: Image du masque RGB (en bas à droite)
ax3 = plt.subplot2grid((3, 2), (1, 1))

# Quatrième graphique: Nouveau graphique supplémentaire qui occupe toute la largeur en bas
ax4 = plt.subplot2grid((3, 2), (2, 0), colspan=2)  # Occupant toute la largeur en bas


# Configuration des axes du premier graphique
ax1.set_xlim(0, 30)
ax1.set_xlabel('Temps (s)')
ax1.set_ylim(-2000, 2000)
ax1.set_ylabel('Amplitude en mL')
ax1.grid()
#Titre du graphique 1
ax1.set_title('Variation du volume en fonction du temps')

# --- Deuxième graphique: Fréquence respiratoire ---
freq_ax = ax2
freq_ax.set_title('Constante respiratoire')
freq_ax.axis('off')

# --- Troisième graphique: Image du masque RGB ---
ax3.axis('off')
ax3.set_title('Masque RGB')

# --- Quatrième graphique: Courbe débit - temps
ax4.set_xlim(0, 30)
ax4.set_xlabel('Temps (s)')
ax4.set_ylim(-2000, 2000)
ax4.set_ylabel('Amplitude en mL')
ax4.grid()
ax4.set_title('Variation du débit en fonction du temps')
#Rend la ligne de la grille qui croise le zéro plus épaisse
ax4.axhline(y=0, color='slategray', linewidth=2)



# animated=True tells matplotlib to only draw the artist when we
# explicitly request it
(ln,) = ax1.plot(x_data, y_data, label='Données brutes', animated=True)
line_filtered, = ax1.plot([], [], label='Données filtrées', color='g')
scatter_peaks = ax1.scatter([], [], color='r', label='Pics', marker='x')
scatter_troughs = ax1.scatter([], [], color='y', label='Creux', marker='o')
scatter_peaks_derivative = ax4.scatter([], [], color='r', label='Pics', marker='x')
scatter_troughs_derivative = ax4.scatter([], [], color='y', label='Creux', marker='o')
line_derivative, = ax4.plot([], [], label='Flow', color='b')
ax1.legend()
ax4.legend()
manager = plt.get_current_fig_manager()
manager.full_screen_toggle()

while flag:
    # A modifier en fonction de la taille des données envoyées
    data = conn.recv(17).decode('ascii')
    
    # Si aucune donnée n'est reçue, arrêter
    if not data:
        break  
    if "END" in data:
        flag = False
        continue
    if (data.__len__() < 17):
        print("data:", data)
    # Remove the \n character
    data = data.replace('\n', '')  
    line = data.replace(',', '.')
    y_value = float(line)
    y_value = -y_value
    
    if flagScale and data:
        scale = y_value
        print("scale:", scale)
        flagScale = False
        # make sure the window is raised, but the script keeps going
        plt.show(block=False)

        # stop to admire our empty window axes and ensure it is rendered at
        # least once.
        #
        # We need to fully draw the figure at its final size on the screen
        # before we continue on so that :
        #  a) we have the correctly sized and drawn background to grab
        #  b) we have a cached renderer so that ``ax.draw_artist`` works
        # so we spin the event loop to let the backend process any pending operations
        plt.pause(0.1)

        # get copy of entire figure (everything inside fig.bbox) sans animated artist
        bg = fig.canvas.copy_from_bbox(fig.bbox)
        # draw the animated artist, this uses a cached renderer
        ax1.draw_artist(ln)
        # show the result to the screen, this pushes the updated RGBA buffer from the
        # renderer to the GUI framework so you can see it
        fig.canvas.blit(fig.bbox)
    
    #Add value to y_data
    y_data = np.append(y_data, y_value-scale)
    #Add value to x_data
    x_data = np.append(x_data, x_data.size/30)
    
    # reset the background back in the canvas state, screen unchanged
    fig.canvas.restore_region(bg)
    # update the artist, neither the canvas state nor the screen have changed
    ln.set_xdata(x_data)
    ln.set_ydata(y_data)
    # re-render the artist, updating the canvas state, but not the screen
    ax1.draw_artist(ln)
    # copy the image to the GUI state, but screen might not be changed yet
    fig.canvas.blit(fig.bbox)
    # flush any pending GUI events, re-painting the screen if needed
    fig.canvas.flush_events()
    # you can put a pause in if you want to slow things down
    # plt.pause(.1)




# Supprimer les valeurs aberrantes
y_data_cleaned = remove_outliers(y_data)

# Appliquer le filtre FIR si assez de données sont présentes
if len(y_data_cleaned) > filter_order * 5:
    y_filtered_data = filtfilt(filter_fir, 1.0, y_data_cleaned)

# Mettre à jour les données filtrées
if len(y_filtered_data) > 0:
    #Afficher les données filtrées
    line_filtered.set_data(x_data[:len(y_filtered_data)], y_filtered_data)
    
    # Détecter les pics et creux dans les données filtrées
    peaks, _ = find_peaks(y_filtered_data, distance=40, width=15)
    troughs, _ = find_peaks(-y_filtered_data, distance=40, width=15)
    # peaks, _ = find_peaks(y_filtered_data, distance=20, width=10)
    # troughs, _ = find_peaks(-y_filtered_data, distance=20, width=10)

    # Mettre à jour les coordonnées des pics et des creux
    scatter_peaks.set_offsets(np.c_[np.array(x_data)[peaks], y_filtered_data[peaks]])
    scatter_troughs.set_offsets(np.c_[np.array(x_data)[troughs], y_filtered_data[troughs]])
    
    dy_dx = np.gradient(y_filtered_data, x_data[:len(y_filtered_data)])
    line_derivative.set_data(x_data[:len(dy_dx)], dy_dx)

    FR_temp = (len(troughs) - 1) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])
    # Détecter les pics et creux sur la dérivée
    peaks_derivative, _ = find_peaks(dy_dx, height=100, distance=int(30 * sampling_rate_kinect_hz / FR_temp)) # Se baser sur la FR pour ajuster la distance entre les pics
    troughs_derivative, _ = find_peaks(-dy_dx, height=100, distance=int(30 * sampling_rate_kinect_hz / FR_temp))

    # Mettre à jour les coordonnées des pics et des creux sur la dérivée
    scatter_peaks_derivative.set_offsets(np.c_[np.array(x_data)[peaks_derivative], dy_dx[peaks_derivative]])
    scatter_troughs_derivative.set_offsets(np.c_[np.array(x_data)[troughs_derivative], dy_dx[troughs_derivative]])
    # Le débit de pointe vaut la valeur de la dérivée aux pics
    peak_flow = dy_dx[peaks_derivative]
    throug_flow = -dy_dx[troughs_derivative]
    # Calculer la moyenne des pics de débit
    peak_flow_mean = np.mean(peak_flow)
    # Calculer la moyenne des creux de débit
    trough_flow_mean = np.mean(throug_flow)



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


# Charger et afficher l'image du masque dans le graphique 3 --- 
try:
    image_path = './runs/obb//predict/IR4OBB.jpg'
    image = Image.open(image_path)
    ax3.imshow(image)
except Exception as e:
    print(f"Erreur lors du chargement de l'image: {e}")
    try:
        image_path = './runs/obb//predict/RGB4OBB.jpg'
        image = Image.open(image_path)
        ax3.imshow(image)
    except Exception as e:  
        print(f"Erreur lors du chargement de l'image: {e}")
    

# Désactiver le mode animé et tracer le graphique complet
ln.set_animated(False)
fig.canvas.draw()  # Forcer un rendu complet du graphique final
plt.show()
# Fermer la connexion
conn.close()

