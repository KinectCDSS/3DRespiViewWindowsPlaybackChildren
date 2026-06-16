# Projet 3DRespiView Windows Playback Children

## Description

Ce projet utilise une caméra Microsoft Kinect ou une caméra Orbbec Femto Bolt pour capturer et analyser les mouvements respiratoires en temps réel. Il permet de mesurer et visualiser les paramètres respiratoires tels que le volume courant, la fréquence respiratoire, le débit et le rapport I/E de manière non invasive.

  

## Architecture du Projet

Le projet est structuré en trois composants principaux :

 - Programme C# : Interaction avec la caméra Kinect : Capture des données de profondeur en temps réel
   
 - BackEnd Flask (Python) : Réception des données, filtrage et calcul des paramètres respiratoire

 - FrontEnd (ReactJs) : Interface utilisateur avec des graphiques interactifs avec Chart.js


## Fonctionnalités

Acquisition en temps réel des mouvements thoraciques  
Filtrage et traitement du signal respiratoire  
Détection automatique des cycles respiratoires (pics et creux)
Calcul et affichage de paramètres respiratoires :
- Fréquence respiratoire (Rpm) 
- Volume courant moyen (mL) 
- Volume minute expiré (L/min) 
-  Temps d'inspiration et d'expiration 
- Rapport I/E 
- Débits de pointe et de creux

Visualisation graphique du volume et du débit respiratoire  
Sauvegarde des graphiques au format PNG  
Affichage de l'image de détection du thorax


## Prérequis

Microsoft Kinect  
Windows 10 64 bits ou supérieur  
.NET Framework 8.0  
Python 3.9.12  
Node.js et npm  

## Installation

 - [ ] Cloner le dépôt

   `git clone https://github.com/sadc-lab/KinectV1-Respiration.git`

Configurer le backend C#

 - [ ] Ouvrir la solution dans Visual Studio

Restaurer les packages NuGet (K4AdotNet, MathNet.Numerics, System.Drawing.Common)

 - [ ] Publier la solution

 - [ ] Installer les dépendances python

   `pip install -r requirements.txt`

 - [ ] Installer les packages npm. Optionnel, utiliser le dockerfile pour créer un conteneur pour le FrontEnd

   `npm install` **OU** `cd FrontEnd` puis `docker build -t frontend . && docker run -d --name frontend -p 5173:5173 frontend` 

 - [ ] Placer dans le dossier publié, le fichier [model_IR](./Kinect_V1/Python_scripts/model_IR.pt), [predict](./Kinect_V1/Python_scripts/predict.py) et le fichier [Backend](./BackEnd/Backend.py) nécessaire à l'éxécution 


## Utilisation

Démarrer le serveur Python (fichier BackEnd.py)

Démarrer le frontend (npm run dev)
 

## Utilisation de l'application

 Ouvrir un navigateur et accéder à http://localhost:5173

Cliquer sur "Lancer l'acquisition" pour démarrer la capture

Visualiser les graphiques de volume et débit en temps réel

Consulter les statistiques respiratoires détaillées

Sauvegarder les graphiques avec le bouton dédié

Quitter l'application avec le bouton correspondant

## Structure du Projet

Kinect_V1/  
│  
├── FrontEnd/  
│   ├── public/  
│   ├── src/  
│   │   ├── App.jsx          - Composant principal  
│   │   ├── chart.jsx        - Graphiques temps réel  
│   │   ├── respiratory.jsx  - Affichage des statistiques  
│   │   ├── chart.css        - Styles spécifiques  
│   │   ├── main.jsx         - Point d'entrée React  
│   │  
│   ├── index.html  
│   ├── vite.config.js  
│   └── package.json  
│  
├── BackEnd/  
│   ├── Backend.py -Fichier python BackEnd  
└── Kinect_V1/  
    └──  Program.cs           - Point d'entrée C#  


## Dépôt GitHub
Il existe deux branches disponibles selon l'utilisation voulue.  
La première **RealTimek4a** pour une utilisation en temps réel avec une caméra branchée  
La seconde **offline** pour une utilisation sur un fichier .mkv  
Une fois la branche sélectionnée, il faut choisir le nuget package en correspondance avec le modèle de la caméra.
K4AdotNet (Kinect) ou K4AdotNet-Femto (Orbbec)


## Entraînement de l'IA
L'application label-studio est utilisée pour réaliser les labels (cf. video) TODO  
Pour réaliser l'entraînement à partir des labels, respecter la structure des dossiers train et valid

## Informations complémentaires
Scripts python disponibles dans le dossier [Python_scripts](./Kinect_V1/Python_scripts/)  
On y retrouve le fichier extract_spiro_from_xml qui permet à partir du fichier xml exporté de l'application EasyOneConnect de créer les fichiers .csv correspondants pour chacun des essais.  
Pour les acquisitions avec l'ancien setup, les fichiers .csv de spiromètres sont avec un autre format. Il existe un fichier old_spiro_csv_clean qui permet de le nettoyer avant de l'utiliser.  
**Le fichier predict.py est nécessaire pour réaliser la prédiction de la ROI**  
**Le fichier model_IR.pt représente les poids du model d'IA**  
Le fichier spiro_plot permet de tracer les courbes à partir de fichier csv en utilisant matplotlib


