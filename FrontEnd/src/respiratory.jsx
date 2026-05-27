import {useState} from 'react';
import {
    Box,
    Typography,
    List,
    ListItem,
    ListItemText,
    FormControlLabel,
    Checkbox,
    Tooltip
} from '@mui/material';
import Grid from '@mui/material/Grid2';
import './chart.css';
import PropTypes from 'prop-types';


const StatsComponent = ({stats}) => {
    const [showVolumes, setShowVolumes] = useState(false);
    const [showInspiration, setShowInspiration] = useState(false);
    const [showExpiration, setShowExpiration] = useState(false);

    return (
        <div style={{
            width: '70vw',
            backgroundColor: "rgb(243,243,243)",
            padding: "1%",
            borderRadius: "2%",
            margin: "1%"
        }}>
            {stats &&
                <Grid container spacing={3} sx={{justifyContent: "space-between"}}>
                    {/* Section texte à gauche */}
                    <Grid size={4}>

                        <div className="statsItemsBloc">
                            <Box>
                                <Typography variant="h5" gutterBottom align="center">
                                    Statistiques Respiratoires :
                                </Typography>
                                <List>
                                    <ListItem style={{paddingTop: 0, paddingBottom: 0, margin: 0}}>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Fréquence respiratoire (Rpm): ${stats['Frequence respiratoire (Rpm)']}`}/>
                                    </ListItem>
                                    <ListItem>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Volume minute expiré (L/min): ${stats['Volume minute expire (L/min)']}`}/>
                                    </ListItem>
                                    <ListItem>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Volume courant moyen (mL): ${stats['Volume courant moyen (mL)']}`}/>
                                    </ListItem>
                                    <ListItem>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Temps moyen inspiration (s): ${stats['Temps moyen inspiration (s)']}`}/>
                                    </ListItem>
                                    <ListItem>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Temps moyen expiration (s): ${stats['Temps moyen expiration (s)']}`}/>
                                    </ListItem>
                                    <ListItem>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Rapport I/E: ${stats['Rapport I/E']}`}/>
                                    </ListItem>
                                    <ListItem>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Débit de pointe moyen (mL/s): ${stats['Debit de pointe moyen (mL/s)']}`}/>
                                    </ListItem>
                                    <ListItem>
                                        <ListItemText style={{lineHeight: 0, margin: 0}}
                                                      primary={`Débit de creux moyen (mL/s): ${stats['Debit de creux moyen (mL/s)']}`}/>
                                    </ListItem>
                                </List>
                            </Box>
                        </div>

                    </Grid>
                    {/* Affichage conditionnel basé sur les switches */}
                    {showVolumes && (<Grid size={2}>
                            <div className="statsItemsBloc">

                                <Typography variant="h6" align="center">Vc :</Typography>
                                <List>
                                    {stats['Volumes (mL)'].map((volume, index) => (
                                        <ListItem key={index}>
                                            <ListItemText primary={`Vc ${index + 1}: ${volume} mL`}/>
                                        </ListItem>
                                    ))}
                                </List>
                            </div>
                        </Grid>
                    )}

                    {showInspiration && (
                        <Grid size={2}>
                            <div className="statsItemsBloc">
                                <Typography variant="h6" align="center">Ti :</Typography>
                                <List>
                                    {stats['Temps inspiration (s)'].map((ti, index) => (
                                        <ListItem key={index}>
                                            <ListItemText primary={`Ti ${index + 1}: ${ti} s`}/>
                                        </ListItem>
                                    ))}
                                </List>
                            </div>
                        </Grid>)}

                    {showExpiration && (
                        <Grid size={2}>
                            <div className="statsItemsBloc">
                                <Typography variant="h6" align="center">Te :</Typography>
                                <List>
                                    {stats['Temps expiration (s)'].map((te, index) => (
                                        <ListItem key={index}>
                                            <ListItemText primary={`Te ${index + 1}: ${te} s`}/>
                                        </ListItem>
                                    ))}
                                </List>
                            </div>
                        </Grid>
                    )}
                    <Grid container direction="column">
                        <Grid size={2} style={{
                            borderColor: "#189ab4",
                            backgroundColor: "#ffffff",
                            border: "0.1rem solid",
                            // position: "absolute",
                            // left: "49.5vw",
                            width: "5vw",
                            justifyContent: "center",
                            display: "flex"
                        }}>

                            {/* Switches pour afficher/masquer les détails */}
                            <div style={{display: "flex", flexDirection: "column"}}>
                                <Tooltip title="Volume courant par cycle">
                                    <FormControlLabel
                                        control={<Checkbox checked={showVolumes}
                                                           onChange={() => setShowVolumes(!showVolumes)}/>}
                                        label="Vc"
                                    />
                                </Tooltip>
                                <Tooltip title="Temps inspiration par cycle">
                                    <FormControlLabel
                                        control={<Checkbox checked={showInspiration}
                                                           onChange={() => setShowInspiration(!showInspiration)}/>}
                                        label="Ti"
                                    />
                                </Tooltip>
                                <Tooltip title="Temps expiratoire par cycle">
                                    <FormControlLabel
                                        control={<Checkbox checked={showExpiration}
                                                           onChange={() => setShowExpiration(!showExpiration)}/>}
                                        label="Te"
                                    />
                                </Tooltip>
                            </div>
                        </Grid>
                    </Grid>
                </Grid>
            }
        </div>
    )
        ;
};

export default StatsComponent;

StatsComponent.propTypes = {
    stats: PropTypes.shape({
        'Frequence respiratoire (Rpm)': PropTypes.number,
        'Volume minute expire (L/min)': PropTypes.number,
        'Volume courant moyen (mL)': PropTypes.number,
        'Temps moyen inspiration (s)': PropTypes.number,
        'Temps moyen expiration (s)': PropTypes.number,
        'Rapport I/E': PropTypes.string,
        'Debit de pointe moyen (mL/s)': PropTypes.number,
        'Debit de creux moyen (mL/s)': PropTypes.number,
    })
};
