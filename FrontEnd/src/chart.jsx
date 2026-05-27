import {useEffect, useState} from 'react';
import {Line} from 'react-chartjs-2';
import Chart from 'chart.js/auto';
import RespiratoryStats from "./respiratory.jsx";
import {Button, LinearProgress, Typography} from "@mui/material";
import {createRef} from "react";
import html2canvas from "html2canvas";


const RealTimeChart = () => {
    const [rawData, setRawData] = useState([]);
    const [filteredData, setFilteredRdata] = useState([]);
    const [flowData, setFlowData] = useState([]);
    const [end, setEnd] = useState(false);
    const [stats, setStats] = useState(null); //TODO
    const [peaks, setPeaks] = useState([]);
    const [troughs, setTroughs] = useState([]);
    const [peaksFlow, setPeaksFlow] = useState([]);
    const [throughsFlow, setthroughsFlow] = useState([]);
    const [streamOpen, setStreamOpen] = useState(false);

    const ref = createRef(null);
    const captureScreenshot = () => {
        html2canvas(ref.current, {
            useCORS: true
        }).then((canvas) => {
            const dataURL = canvas.toDataURL("image/png");
            const a = document.createElement("a");
            a.href = dataURL;
            a.download = "screenshot.png";  // Nom du fichier de téléchargement
            a.click();  // Simuler le clic pour télécharger l'image
        });
    };

    useEffect(() => {
        if (streamOpen) {
            return;
        }
        // Créer un objet EventSource pour écouter les événements SSE
        const eventSource = new EventSource('http://localhost:8000/stream');  // URL du serveur Flask
        setStreamOpen(true);
        let rawDataFlag = true;
        let filteredDataFlag = false;
        let flowDataFlag = false;
        // Écouter l'événement "message" pour récupérer les données
        eventSource.onmessage = function (event) {

            // Si le message "END" est reçu, fermer la connexion
            if (event.data === "END") {
                console.log("Fin des données, fermeture de la connexion.");
                eventSource.close();
                setEnd(true);
            } else {
                if (event.data === "ENDRAW") {
                    console.log("Fin des données brutes.");
                    rawDataFlag = false;
                    filteredDataFlag = true;
                }
                if (event.data === "ENDFILTERED") {
                    console.log("Fin des données filtrées.");
                    filteredDataFlag = false;
                    flowDataFlag = true;
                }
                const newData = parseInt(event.data);
                if (rawDataFlag) {
                    setRawData((prevData) => [...prevData, newData]);
                }
                if (filteredDataFlag) {
                    setFilteredRdata((prevData) => [...prevData, newData]);
                }
                if (flowDataFlag) {
                    setFlowData((prevData) => [...prevData, newData]);
                }

            }
        }
    }, []);

    useEffect(() => {
        if (end) {
            console.log("Récupération des donneés mathématiques.");
            // Faire un appel GET sur l'API Flask pour récupérer les données
            fetch('http://localhost:8000/stats')
                .then(response => response.json())
                .then(data => {
                    setStats(data);  // Mettre à jour l'état avec les données récupérées
                    setPeaks([]);
                    for (let i = 0; i < data["Cooordonees x des pics"].length; i++) {
                        setPeaks((prevPeaks) => [...prevPeaks, {
                            x: data["Cooordonees x des pics"][i],
                            y: data["Cooordonees y des pics"][i]
                        }]);
                    }
                    setTroughs([]);
                    for (let i = 0; i < data["Cooordonees x des creux"].length; i++) {
                        setTroughs((prevTroughs) => [...prevTroughs, {
                            x: data["Cooordonees x des creux"][i],
                            y: data["Cooordonees y des creux"][i]
                        }]);
                    }
                    setPeaksFlow([]);
                    for (let i = 0; i < data["Coordonnees x des pics de debit"].length; i++) {
                        setPeaksFlow((prevPeaksFlow) => [...prevPeaksFlow, {
                            x: data["Coordonnees x des pics de debit"][i],
                            y: data["Coordonnees y des pics de debit"][i]
                        }]);
                    }
                    setthroughsFlow([]);
                    for (let i = 0; i < data["Coordonnees x des creux de debit"].length; i++) {
                        setthroughsFlow((prevThroughsFlow) => [...prevThroughsFlow, {
                            x: data["Coordonnees x des creux de debit"][i],
                            y: data["Coordonnees y des creux de debit"][i]
                        }]);
                    }
                })
                .catch(error => console.error('Erreur de récupération des statistiques:', error));
        }
    }, [end]);

    const chartDataVolume = {
        labels: Array.from({length: 900}, (_, index) => (index / 30)),
        datasets: [
            {
                label: 'Données brutes',
                data: rawData,
                fill: false,
                borderColor: 'rgba(75, 192, 192, 1)',  // Bleu moyen pour les données brutes
                backgroundColor: '#9BD0F5',
                tension: 0.1,
                pointRadius: 0,  // Masquer les points (points invisibles)
            },
            {
                label: 'Données filtrées',
                data: filteredData,
                fill: false,
                borderColor: 'rgb(79,169,118)',  // Bleu clair pour les données filtrées
                backgroundColor: '#71eaa5',
                tension: 0.1,
                pointRadius: 0,  // Masquer les points (points invisibles)
            },
            {
                label: 'Pics',
                data: peaks,
                fill: false,
                borderColor: 'rgba(255, 159, 64, 1)',  // Jaune/orange pour les pics
                backgroundColor: '#FFC107',
                tension: 0.1,
                showLine: false,  // Cette option est cruciale pour ne pas relier les points par une ligne
                pointRadius: 10,
                pointHoverRadius: 20,
            },
            {
                label: 'Creux',
                data: troughs,
                fill: false,
                borderColor: 'rgba(255, 99, 132, 1)',  // Rouge pour les creux
                backgroundColor: '#FF5252',
                tension: 0.1,
                showLine: false,  // Cette option est cruciale pour ne pas relier les points par une ligne
                pointRadius: 10,
                pointHoverRadius: 20,
            },
        ],
    };

    const chartDataFlow = {
        labels: Array.from({length: 900}, (_, index) => (index / 30)),
        datasets: [
            {
                label: 'Flow',
                data: flowData,
                fill: false,
                borderColor: 'rgba(75, 192, 192, 1)',  // Bleu moyen pour le flow
                backgroundColor: '#9BD0F5',
                tension: 0.1,
                pointRadius: 0,  // Masquer les points (points invisibles)
            },
            {
                label: 'Pics',
                data: peaksFlow,
                fill: false,
                borderColor: 'rgba(255, 159, 64, 1)',  // Jaune/orange pour les pics
                backgroundColor: '#FFC107',
                tension: 0.1,
                showLine: false,  // Cette option est cruciale pour ne pas relier les points par une ligne
                pointRadius: 10,
                pointHoverRadius: 20,
            },
            {
                label: 'Creux',
                data: throughsFlow,
                fill: false,
                borderColor: 'rgba(255, 99, 132, 1)',  // Rouge pour les creux
                backgroundColor: '#FF5252',
                tension: 0.1,
                showLine: false,  // Cette option est cruciale pour ne pas relier les points par une ligne
                pointRadius: 10,
                pointHoverRadius: 20,
            },
        ],
    };


    const optionsVolume = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Temps (s)',  // Titre de l'axe X
                },
                ticks: {
                    callback: function (value, index) {
                        let label = '';
                        if (index % 10 === 0) {
                            label = Math.round(this.getLabelForValue(value));
                        } else {
                            label = '';
                        }
                        return label;
                    }
                }
            },
            y: {
                title: {
                    display: true,
                    text: 'Amplitude (mL)'  // Titre de l'axe Y
                },
                //min: -2000,
                //max: 2000,
            }
        },
        animation: {
            duration: 0,  // Définir la durée de l'animation à 0 pour désactiver l'animation
            easing: 'linear',  // Optionnel, définit le type d'animation si jamais vous voulez en laisser une
        },
        plugins: {
            title: {
                display: true,
                text: 'Variation du volume en fonction du temps',  // Titre du graphique
                font: {
                    size: 20,
                }
            },
            tooltip: {
                callbacks: {
                    label: (tooltipItem) => {
                        return tooltipItem.dataset.label + ': (' + (tooltipItem.parsed.x / 30).toFixed(2) + ', ' + (tooltipItem.parsed.y).toFixed(2) + ')';
                    },
                },
            },
        },
    };


    const optionsFlow = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: {
                title: {
                    display: true,
                    text: 'Temps (s)'  // Titre de l'axe X
                },
                ticks: {
                    callback: function (value, index) {
                        let label = '';
                        if (index % 10 === 0) {
                            label = Math.round(this.getLabelForValue(value));
                        } else {
                            label = '';
                        }
                        return label;
                    }
                }
            },
            y: {
                title: {
                    display: true,
                    text: 'Amplitude (mL)',  // Titre de l'axe Y
                },
                //min: -2000,
                //max: 2000,
            }
        },
        animation: {
            duration: 0,  // Définir la durée de l'animation à 0 pour désactiver l'animation
            easing: 'linear',  // Optionnel, définit le type d'animation si jamais vous voulez en laisser une
        },
        plugins: {
            title: {
                display: true,
                text: 'Variation du débit en fonction du temps',  // Titre du graphique
                font: {
                    size: 20,
                }
            },
            tooltip: {
                callbacks: {
                    label: (tooltipItem) => {
                        return tooltipItem.dataset.label + ': (' + (tooltipItem.parsed.x / 30).toFixed(2) + ', ' + (tooltipItem.parsed.y).toFixed(2) + ')';
                    },
                },
            },
        },
    };


    const closeAll = async () => {
        try {
            // Envoi de la requête fetch
            const response = await fetch('http://localhost:8000/close', {
                method: 'POST',  // Assure-toi que la méthode soit correcte (POST ou GET)
                headers: {
                    'Content-Type': 'application/json', // Si nécessaire, selon ton API
                },
                // body: JSON.stringify(data), // Si tu as besoin d'envoyer des données
            });

            if (!response.ok) {
                // Vérifie si la requête a échoué (code HTTP différent de 2xx)
                throw new Error(`Erreur lors de la requête: ${response.statusText}`);
            }

            const data = await response.json(); // Récupère la réponse sous forme JSON (si nécessaire)
            console.log('Réponse du serveur:', data);

        } catch (error) {
            // Gérer les erreurs (par exemple, problème réseau, erreur API)
            console.error('Erreur lors de la requête:', error);
        }
    };

    return (
        <div ref={ref} style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            height: '95vh',
            width: '99vw'
        }}>
            {/* Graphique en haut de la page */}
            <div style={{width: '98vw', height: '30vh'}}>
                <Line data={chartDataVolume} options={optionsVolume}/>
            </div>
            {/* Graphique du flow en bas de la page */}
            <div style={{width: '98vw', height: '30vh'}}> {/* Conteneur parent avec taille dynamique */}
                <Line data={chartDataFlow} options={optionsFlow}/>
            </div>
            <div style={{display: "flex", justifyContent: "space-between"}}>
                <RespiratoryStats stats={stats}/>
                <div style={{
                    width: '50%',
                    marginRight: "10vh",
                    display: "flex",
                    flexDirection: "row",
                    justifyContent: "space-evenly"
                }}>
                    <div style={{display: "flex", flexDirection: "column"}}>
                        <img src="http://localhost:8000/image/IR4OBB.jpg" alt="Image IR4OBB" style={{height: "25vh", margin: "auto"}} onError={(e) => {
                            e.target.onerror = null; // Prevent infinite loop
                            setTimeout(() => {
                                e.target.src = "http://localhost:8000/image/IR4OBB.jpg";
                            }, 3000); // Retry after 5 seconds
                        }}/>
                        {/*<img*/}
                        {/*    src="https://img.freepik.com/photos-gratuite/gros-plan-vertical-tire-belle-rose-sauvage-rose-flou_181624-32482.jpg"*/}
                        {/*    alt="Image IR4OBB" style={{height: "25vh", margin: "auto"}}/>*/}
                        <Typography variant="h6" align="center">Région du thorax détectée</Typography>
                    </div>

                    <div style={{display: "flex", flexDirection: "column", justifyContent: "space-evenly"}}>
                        <Button
                            variant="contained"
                            onClick={captureScreenshot}
                            sx={{
                                backgroundColor: '#4caf50',
                                '&:hover': {backgroundColor: '#388e3c'},
                                fontWeight: 'bold',
                                borderRadius: 10,
                            }}>
                            Sauvegarder le graphique
                        </Button>

                        <Button
                            variant="contained"
                            onClick={closeAll}
                            sx={{
                                backgroundColor: '#D7707E',
                                '&:hover': {backgroundColor: '#7c041b'},
                                fontWeight: 'bold',
                                borderRadius: 10,
                            }}>
                            Quitter l&#39;application
                        </Button>
                    </div>
                </div>
            </div>

        </div>
    )
        ;
}

export default RealTimeChart;