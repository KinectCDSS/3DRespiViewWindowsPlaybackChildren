import RealTimeChart from './chart.jsx';
import { useState } from "react";
import { Button, Box, Typography, CircularProgress, TextField } from "@mui/material";
import { PlayArrow } from "@mui/icons-material";

function App() {
    const [status, setStatus] = useState('');
    const [filename, setFilename] = useState('');
    const [startTime, setStartTime] = useState('0'); // Nouvelle case pour le temps de départ en secondes
    const [showChart, setShowChart] = useState(false);
    const [loading, setLoading] = useState(false);

    const handleActionClick = async () => {
        if (!filename.trim()) {
            setStatus("Erreur : Veuillez renseigner un nom de fichier valide.");
            return;
        }

        setLoading(true);
        setStatus('');
        try {
            const response = await fetch('http://localhost:8000/run-analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    filename: filename.trim(),
                    start_time: parseFloat(startTime) || 0
                })
            });
            const data = await response.json();

            if (response.ok) {
                setStatus(data.message);
                // Court délai de transition pour l'initialisation du stream
                await new Promise(r => setTimeout(r, 1000));
                setShowChart(true);
            } else {
                setStatus('Erreur : ' + data.message);
                setShowChart(false);
            }
        } catch (error) {
            setStatus('Erreur de communication avec le serveur local');
            setShowChart(false);
        } finally {
            setLoading(false);
        }
    };

    const checkIsOffline = !filename.toLowerCase().includes('.mkv');

    return (
        <>
            {!showChart ?
                <Box
                    display="flex"
                    flexDirection="column"
                    alignItems="center"
                    justifyContent="center"
                    minHeight="100vh"
                    sx={{ backgroundColor: '#f4f4f4', padding: 3 }}>

                    <Typography variant="h4" sx={{ marginBottom: 4, fontWeight: 'bold', color: '#333', textAlign: 'center' }}>
                        Application Volume Courant 3DRespiView
                    </Typography>

                    <Box display="flex" gap={2} sx={{ marginBottom: 4 }}>
                        <TextField
                            label="Fichier d'entrée (.mkv, .sta, .csv)"
                            variant="outlined"
                            value={filename}
                            onChange={(e) => setFilename(e.target.value)}
                            sx={{ width: '320px', backgroundColor: '#fff' }}
                        />

                        <TextField
                            label="Temps de départ (s)"
                            variant="outlined"
                            type="number"
                            value={startTime}
                            onChange={(e) => setStartTime(e.target.value)}
                            sx={{ width: '150px', backgroundColor: '#fff' }}
                        />
                    </Box>

                    <Button
                        variant="contained"
                        disabled={loading}
                        endIcon={loading ? <CircularProgress size={24} color="inherit" /> : <PlayArrow />}
                        onClick={handleActionClick}
                        sx={{
                            backgroundColor: checkIsOffline ? '#2e7d32' : '#3f51b5',
                            '&:hover': { backgroundColor: checkIsOffline ? '#1b5e20' : '#303f9f' },
                            fontWeight: 'bold',
                            padding: '14px 32px',
                            fontSize: '1rem',
                            borderRadius: '6px'
                        }}>
                        {loading ? 'Traitement en cours...' : 'Lancer le suivi respiratoire'}
                    </Button>

                    {status && (
                        <Typography variant="body1" sx={{ color: status.startsWith('Erreur') ? '#d32f2f' : '#2e7d32', fontWeight: 'bold', marginTop: 3 }}>
                            {status}
                        </Typography>
                    )}
                </Box>
                :
                <>
                    <div>
                        <RealTimeChart filename={filename.trim()} isOffline={checkIsOffline} />
                    </div>
                </>
            }
        </>
    );
}

export default App;