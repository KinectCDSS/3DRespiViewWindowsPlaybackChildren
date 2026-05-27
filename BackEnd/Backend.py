import socket
import numpy as np
from scipy.signal import find_peaks, firwin, filtfilt
from flask import Flask, Response, jsonify, send_from_directory
from flask_cors import CORS
import csv
import os
import subprocess
import psutil

# "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk http://localhost:5173/ --edge-kiosk-type=fullscreen

app = Flask(__name__, static_folder='./')
CORS(app)  # Active CORS pour toutes les routes

# Configuration du socket
host = '127.0.0.1'
port = 5000

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

# Conception du filtre passe-bas FIR
filter_fir = firwin(numtaps=filter_order + 1, cutoff=frequency_cutoff_hz, fs=sampling_rate_kinect_hz)

# Ajout d'une fonction pour stocker les données non filtrées dans un fichier CSV
def store_non_filtered_data_in_csv(data, filename='non_filtrered_data.csv'):
    output_dir = './Output'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        for value in data:
            writer.writerow([value])  # Écrire chaque valeur de 'data' dans la première colonne
    print(f"Données non filtrées stockées dans {filepath}")

# Ajout d'une fonction pour stocker les données filtrées dans un fichier CSV
def store_data_in_csv(data, filename='filtered_data.csv'):
    output_dir = './Output'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        for value in data:
            writer.writerow([value])  # Écrire chaque valeur de 'data' dans la première colonne
    print(f"Données filtrées stockées dans {filepath}")

# Suppression des fichiers CSV précédents dans le dossier ./Output
output_dir = './Output'
non_filtered_path = os.path.join(output_dir, 'non_filtrered_data.csv')
filtered_path = os.path.join(output_dir, 'filtered_data.csv')

# --- Variables pour le suivi des données ---
x_data = np.array([])
y_data = np.array([])
y_filtered_data = np.array([])
dy_dx = np.array([])

# Suppression de l'option de fermeture immédiate
flag = True
flagScale = True
scale = 0
conn=None

# Fonction pour générer les données en temps réel
def generate_data():
    global x_data, y_data, scale, flag, flagScale, y_filtered_data, dy_dx
    conn = None
    try:
        # Initialisation du socket pour accepter une seule connexion
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Vérifier qu'aucun socket ne soit ouvert avant de lier
            try:
                sock.bind((host, port))
            except socket.error as e:
                print(f"Erreur de liaison du socket: {e}")
                return
            sock.listen(1)  # Attente d'une seule connexion
            print(f"En attente de connexion sur {host}:{port}...")
            conn, addr = sock.accept()
            print(f"Connexion établie avec {addr}")

            while flag:
                # A modifier en fonction de la taille des données envoyées
                data = conn.recv(2048).decode('ascii')

                # Si aucune donnée n'est reçue, arrêter
                if not data:
                    break  
                if "END" in data:
                    flag = False
                    sock.close()
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

                # Add value to y_data
                y_data = np.append(y_data, y_value - scale)
                # Add value to x_data
                x_data = np.append(x_data, x_data.size / 30)

                # Send data in SSE format
                yield f"data: {y_value - scale}\n\n"
            yield "data: ENDRAW\n\n"

    finally:
        if conn:
            #conn.shutdown()
            conn.close()
            sock.close()
            print("Connexion fermée")
    # --- Filtrage des données ---
    # Supprimer les valeurs aberrantes
    y_data_cleaned = remove_outliers(y_data)

    # Stocke les données non filtrées
    store_non_filtered_data_in_csv(y_data_cleaned)

    # Appliquer le filtre FIR si assez de données sont présentes
    if len(y_data_cleaned) > filter_order * 5:
        y_filtered_data = filtfilt(filter_fir, 1.0, y_data_cleaned)
        store_data_in_csv(y_filtered_data)  # Stocke les données filtrées
        # Parcourir les données filtées pour les envoyer
        for value in y_filtered_data:
            yield f"data: {value}\n\n"
        yield "data: ENDFILTERED\n\n"
        # Dériver le signal filtré pour obtenir le flow
        dy_dx = np.gradient(y_filtered_data, x_data[:len(y_filtered_data)])
        # Parcourir les données de débit pour les envoyer
        for value in dy_dx:
            yield f"data: {value}\n\n"
        # Envoyer un message de fin
        yield "data: END\n\n"

    
   

@app.route('/stream')
def stream():
    return Response(generate_data(), content_type='text/event-stream')

@app.route('/stats', methods=['GET'])
def send_stats():
    global y_filtered_data, dy_dx, x_data
     # Mettre à jour les données filtrées
    if len(y_filtered_data) > 0:
        # Détecter les pics et creux dans les données filtrées
        peaks, _ = find_peaks(y_filtered_data, distance=40, width=15)
        troughs, _ = find_peaks(-y_filtered_data, distance=40, width=15)

        FR_temp = (len(troughs) - 1) * 60 / (x_data[troughs[-1]] - x_data[troughs[0]])
        # Détecter les pics et creux sur la dérivée
        peaks_derivative, _ = find_peaks(dy_dx, height=100, distance=int(30 * sampling_rate_kinect_hz / FR_temp)) # Se baser sur la FR pour ajuster la distance entre les pics
        troughs_derivative, _ = find_peaks(-dy_dx, height=100, distance=int(30 * sampling_rate_kinect_hz / FR_temp))
        
        # Le débit de pointe vaut la valeur de la dérivée aux pics
        peak_flow = dy_dx[peaks_derivative]
        troughs_flow = -dy_dx[troughs_derivative]
        # Calculer la moyenne des pics de débit
        peak_flow_mean = np.mean(peak_flow)
        troughs_flow_mean = np.mean(troughs_flow)




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


    # Créer un dictionnaire avec toutes les données à envoyer
    stats = {
        "Frequence respiratoire (Rpm)": round(FR),
        "Volume minute expire (L/min)": round(volume_minute / 1000, 2),  # Conversion de mL/min à L/min
        "Volume courant moyen (mL)": round(np.mean(volume)),
        "Temps moyen inspiration (s)": round(inspiration_time_mean, 1),
        "Temps moyen expiration (s)": round(expiration_time_mean, 1),
        "Rapport I/E": f"1/{round(expiration_time_mean/inspiration_time_mean, 1)}",
        "Debit de pointe moyen (mL/s)": round(peak_flow_mean),
        "Debit de creux moyen (mL/s)": round(troughs_flow_mean),
        "Volumes (mL)": [round(v) for v in volume],
        "Temps inspiration (s)": [round(ti, 2) for ti in inspiration_time],
        "Temps expiration (s)": [round(te, 2) for te in expiration_time],
        "Cooordonees x des pics": [x_data[p] for p in peaks],
        "Cooordonees y des pics": [y_filtered_data[p] for p in peaks],
        "Cooordonees x des creux": [x_data[t] for t in troughs],
        "Cooordonees y des creux": [y_filtered_data[t] for t in troughs],
        "Coordonnees x des pics de debit": [x_data[p] for p in peaks_derivative],
        "Coordonnees y des pics de debit": [dy_dx[p] for p in peaks_derivative],
        "Coordonnees x des creux de debit": [x_data[t] for t in troughs_derivative],
        "Coordonnees y des creux de debit": [dy_dx[t] for t in troughs_derivative]
    }

    # Retourner les données sous forme de réponse JSON
    return jsonify(stats)

@app.route('/run-exe', methods=['GET'])
def run_exe():
    try:
        # Obtenir le chemin du répertoire où se trouve le fichier Flask
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Construire le chemin relatif vers le fichier .exe
        file_path = os.path.join(current_dir, 'Kinect_V1.exe')
        # Vérifier si le fichier existe
        if not os.path.exists(file_path):
            return jsonify({"message": f"Le fichier {file_path} n'existe pas."}), 404

        # Définir le répertoire de travail dans lequel exécuter l'EXE
        cwd = current_dir  # Le répertoire de travail sera celui où se trouve le script Flask

        # Utiliser subprocess.run avec le paramètre cwd pour changer le répertoire de travail
        subprocess.Popen([file_path], cwd=cwd)
        return jsonify({"message": "Fichier .exe exécuté avec succès!"}), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route('/image/<path:filename>')
def get_image(filename):
    # Assurez-vous que ce dossier existe
    # Serve le fichier image depuis le dossier 'runs/obb/predict'
    current_dir = os.path.dirname(os.path.abspath(__file__))
    RUNS_DIR = os.path.join(current_dir, 'runs/obb/predict')
    #exit()
#    kill_processes_using_port(5000)
    return send_from_directory(RUNS_DIR, filename)

def exit():
    print("Le serveur Flask va se fermer maintenant.")
    os.kill(os.getpid(), 9)

# Route /close pour gérer la fermeture
@app.route('/close', methods=['POST'])
def close():
    try:
        # Ici tu peux mettre le code pour fermer ce que tu veux fermer
        # Par exemple, arrêter un processus, fermer des connexions, etc.
        # Pour l'exemple, on va juste retourner une réponse JSON.

        #Fermer le navigateur msedge
        os.system("taskkill /f /im msedge.exe")
        kill_processes_using_port(5000)
        
        response = {
            'status': 'success',
            'message': 'Fermeture réussie'
        }
        return jsonify(response), 200

    except Exception as e:
        # Gestion des erreurs en cas de problème
        response = {
            'status': 'error',
            'message': str(e)
        }
        return jsonify(response), 500

def kill_processes_using_port(port):
    # Exécuter la commande netstat pour trouver les PID associés au port spécifié
    command = f'netstat -ano | findstr {port}'
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    
    # Analyser chaque ligne de la sortie
    for line in result.stdout.splitlines():
        parts = line.split()
        
        # Le PID est le dernier élément de chaque ligne
        pid = parts[-1]
        
        try:
            # Tuer le processus en utilisant le PID
            process = psutil.Process(int(pid))
            print(f"Tuer le processus PID {pid}")
            process.terminate()  # Utiliser process.kill() si nécessaire pour forcer l'arrêt
        except psutil.NoSuchProcess:
            print(f"Le processus avec le PID {pid} n'existe plus.")
        except psutil.AccessDenied:
            print(f"Permission refusée pour tuer le processus avec le PID {pid}.")
    
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8000)
