import RealTimeChart from './chart.jsx';
import {useState} from "react";
import {Button, Box, Typography, CircularProgress} from "@mui/material";
import {PlayArrow} from "@mui/icons-material";

function App() {
    const [status, setStatus] = useState('');
    const [showChart, setShowChart] = useState(false);  // Nouvel état pour gérer l'affichage du chart TODO
    const [loading, setLoading] = useState(false);  // Etat pour gérer le statut de chargement

    const handleClick = async () => {
        setLoading(true);
        try {
            const response = await fetch('http://localhost:8000/run-exe');
            const data = await response.json();

            if (response.ok) {
                setStatus(data.message);
            } else {
                setStatus('Erreur : ' + data.message);
                setShowChart(false);  // Ne pas afficher le chart si erreur
            }
        } catch (error) {
            console.log(error);
            setStatus('Erreur lors de la connexion au serveur');
            setShowChart(false);  // Ne pas afficher le chart en cas d'erreur
        } finally {
            await new Promise(r => setTimeout(r, 2000));
            setLoading(false);
            setShowChart(true);  // Afficher le chart après succès
        }
    };

    return (
        <>
            {!showChart ?
                <Box
                    display="flex"
                    flexDirection="column"
                    alignItems="center"
                    justifyContent="center"
                    minHeight="100vh"
                    sx={{backgroundColor: '#f4f4f4', padding: 3}}>

                    <Typography variant="h4" sx={{marginBottom: 3, fontWeight: 'bold', color: '#333'}}>
                        Application Volume Courant Kinect
                    </Typography>

                    <Button
                        variant="contained"
                        endIcon={loading ? <CircularProgress size={24} color="inherit"/> : <PlayArrow/>}
                        onClick={handleClick}
                        sx={{
                            backgroundColor: '#3f51b5',
                            '&:hover': {backgroundColor: '#303f9f'},
                            fontWeight: 'bold',
                            padding: '10px 20px',
                            marginBottom: 2
                        }}>
                        {'Lancer l\'acquisition'}
                    </Button>


                    {status && (
                        <Typography variant="body1" sx={{color: '#d32f2f', fontWeight: 'bold'}}>
                            {status}
                        </Typography>
                    )}
                </Box>
                :
                <>
                    {/* Ref uniquement pour le graphique */}
                    <div>
                        <RealTimeChart/>
                    </div>
                </>
            }
        </>
    );
}

export default App;
