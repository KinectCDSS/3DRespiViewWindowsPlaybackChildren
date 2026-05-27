using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using K4AdotNet;
using K4AdotNet.Record;

// Base path = get current directory
string currentDirectory = Directory.GetCurrentDirectory();
string outputDirectoryPath = $@"{currentDirectory}\Output";
string mkvPath = currentDirectory + @"\Input";
int seconds = 0;
string mkvNameFile = "";

// --- INTERCEPTION DES ARGUMENTS DU BACKEND ---
if (args.Length >= 2)
{
    mkvNameFile = args[0];
    if (int.TryParse(args[1], out int parsedSeconds))
    {
        seconds = parsedSeconds;
    }
    Console.WriteLine($"[C#] Paramètres reçus -> Vidéo: {mkvNameFile}.mkv, Départ: {seconds} secondes");
}
else
{
    // Mode de repli au cas où le binaire est exécuté à la main
    Console.WriteLine("Entrez le nom du fichier MKV :");
    mkvNameFile = Console.ReadLine();

    Console.WriteLine("Entrez le nombre de secondes à attendre avant de commencer l'enregistrement :");
    string secondsUser = Console.ReadLine();
    if (!string.IsNullOrEmpty(secondsUser))
    {
        seconds = int.Parse(secondsUser);
    }
}

// Construction du chemin définitif vers la vidéo d'entrée
mkvPath = $@"{mkvPath}\{mkvNameFile}.mkv";

List<PointF> pointsJoints2DPixelDepthOneFrame = new List<PointF>();
List<PointF> pointsJoints2DPixelRGBOneFrame = new List<PointF>();
List<double> surfaceList = new List<double>();
int countMaskPixels = 0;
List<int> pixelsIndexMask = new List<int>();
List<double> volumeList = new List<double>();

string server = "127.0.0.1";
int port = 5000;
bool connected = false;

string pythonExePath = "python";

while (!connected)
{
    try
    {
        using (TcpClient client = new TcpClient(server, port))
        using (NetworkStream stream = client.GetStream())
        {
            connected = true;
            Directory.CreateDirectory(outputDirectoryPath);

            // Playback mode
            using (var playback = new Playback(mkvPath))
            {
                RecordConfiguration recordConfig;
                playback.GetRecordConfiguration(out recordConfig);

                K4AdotNet.Sensor.Calibration deviceCalibration;
                playback.GetCalibration(out deviceCalibration);

                Console.WriteLine($"Depth Mode: {recordConfig.DepthMode}");
                Console.WriteLine($"Color Resolution: {recordConfig.ColorResolution}");
                Console.WriteLine($"Color Format: {recordConfig.ColorFormat}");
                Console.WriteLine($"FPS: {recordConfig.CameraFps}");

                K4AdotNet.Sensor.Capture sensorCapture;

                // Saut au timestamp spécifié (ex: 28 secondes)
                playback.SeekTimestamp(Microseconds64.FromSeconds(seconds), PlaybackSeekOrigin.Begin);

                int imageCount = 0;
                int height_depth = deviceCalibration.DepthCameraCalibration.ResolutionHeight;
                int width_depth = deviceCalibration.DepthCameraCalibration.ResolutionWidth;

                while (imageCount < 960)
                {
                    playback.TryGetNextCapture(out sensorCapture);

                    if (sensorCapture != null && sensorCapture.ColorImage != null && sensorCapture.DepthImage != null && sensorCapture.IRImage != null)
                    {
                        imageCount++;

                        var colorImage = sensorCapture.ColorImage;
                        var depthImage = sensorCapture.DepthImage;
                        var irImage = sensorCapture.IRImage;

                        byte[] colorData = new byte[colorImage.SizeBytes];
                        colorImage.CopyTo(dst: colorData);

                        short[] depthData = new short[height_depth * width_depth];
                        depthImage.CopyTo(dst: depthData);

                        byte[] irData = new byte[irImage.SizeBytes];
                        irImage.CopyTo(dst: irData);

                        // Analyse YOLO/OBB à la 30ème frame relative après le saut temporel
                        if (imageCount == 30)
                        {
                            string rgbname = $@"{outputDirectoryPath}\RGB4OBB.jpg";
                            string irname = $@"{outputDirectoryPath}\IR4OBB.jpg";
                            long imageBufferSize = colorImage.SizeBytes;
                            long imageIRBufferSize = irImage.SizeBytes;

                            using (FileStream fileObject = new FileStream(rgbname, FileMode.Create, FileAccess.Write))
                            {
                                fileObject.Write(colorData, 0, (int)imageBufferSize);
                            }

                            SaveIRImage(irData, irImage, irname);
                            PredictOBB(currentDirectory, pythonExePath, deviceCalibration, depthImage);

                            foreach (PointF point in pointsJoints2DPixelDepthOneFrame)
                            {
                                var point2D = new K4AdotNet.Float2(point.X, point.Y);
                                float depthValue = depthData[(int)point2D.Y * width_depth + (int)point2D.X];
                                var point2DRGB = deviceCalibration.Convert2DTo2D(point2D, depthValue, K4AdotNet.Sensor.CalibrationGeometry.Depth, K4AdotNet.Sensor.CalibrationGeometry.Color);
                                Console.WriteLine($"Point RGB : {point2DRGB.Value.X}, {point2DRGB.Value.Y}");
                                pointsJoints2DPixelRGBOneFrame.Add(new PointF((int)Math.Round(point2DRGB.Value.X), (int)Math.Round(point2DRGB.Value.Y)));
                            }

                            SaveAllMasks(deviceCalibration, depthImage, width_depth, height_depth, outputDirectoryPath, pointsJoints2DPixelDepthOneFrame, pointsJoints2DPixelRGBOneFrame, rgbname);

                            Bitmap maskRead = new Bitmap($@"{outputDirectoryPath}\RGB_transformed.png");

                            for (int y = 0; y < maskRead.Height; y++)
                            {
                                for (int x = 0; x < maskRead.Width; x++)
                                {
                                    Color pixelColor = maskRead.GetPixel(x, y);
                                    if (pixelColor.R == 255 && pixelColor.G == 0 && pixelColor.B == 0)
                                    {
                                        int pixelIndex = y * maskRead.Width + x;
                                        pixelsIndexMask.Add(pixelIndex);
                                        countMaskPixels += 1;
                                    }
                                }
                            }

                            SurfaceDepthsPixels(pixelsIndexMask, surfaceList, deviceCalibration, depthData, width_depth, height_depth);
                        }

                        if (imageCount > 60)
                        {
                            double volume_new = 0;
                            for (int i = 0; i < surfaceList.Count; i++)
                            {
                                double pixel_k_profondeur = depthData[pixelsIndexMask[i]];
                                double volume_pixel = surfaceList[i] * pixel_k_profondeur;
                                volume_new += volume_pixel;
                            }

                            double volumeInmL = volume_new / 1000;
                            volumeList.Add(volumeInmL);
                            string formattedNumber = volumeInmL.ToString("000000.000000000");
                            Console.WriteLine($"Volume pour la frame {imageCount}: {formattedNumber} mL");

                            byte[] message = Encoding.ASCII.GetBytes(formattedNumber + "\n");
                            stream.Write(message, 0, message.Length);
                        }
                    }
                }
                Console.WriteLine($"\rStop Recording. {imageCount} images captured.");
                byte[] endMessage = Encoding.ASCII.GetBytes("END\n");
                stream.Write(endMessage, 0, endMessage.Length);

                stream.Close();
                client.Close();
            }
        }
    }
    catch (Exception ex)
    {
        Console.WriteLine($"Failed to connect to the server: {ex.Message}");
        Console.WriteLine("Retrying in 1 seconds...");
        System.Threading.Thread.Sleep(1000);
    }
}

static void SaveIRImage(byte[] irData, K4AdotNet.Sensor.Image irImage, string irname)
{
    List<double> irValues = new List<double>();
    for (int i = 0; i < irData.Length / 2; i++)
    {
        short irValue = BitConverter.ToInt16(irData, i * 2);
        irValues.Add(irValue);
    }

    irValues.Sort();

    double Q1 = MathNet.Numerics.Statistics.Statistics.Quantile(irValues, 0.05);
    double Q3 = MathNet.Numerics.Statistics.Statistics.Quantile(irValues, 0.95);
    double IQR = Q3 - Q1;

    double lowerThreshold = Q1 - 1.5 * IQR;
    double upperThreshold = Q3 + 1.5 * IQR;

    short minValue = (short)lowerThreshold;
    short maxValue = (short)upperThreshold;

    byte[] normalizedIRData = new byte[irImage.WidthPixels * irImage.HeightPixels];
    for (int i = 0; i < irData.Length / 2; i++)
    {
        short irValue = BitConverter.ToInt16(irData, i * 2);

        if (irValue < lowerThreshold || irValue > upperThreshold)
        {
            irValue = (short)((lowerThreshold + upperThreshold) / 2);
        }

        byte normalizedValue = (byte)((irValue - minValue) * 255 / (maxValue - minValue));
        normalizedIRData[i] = normalizedValue;
    }

    var bitmap = new Bitmap(irImage.WidthPixels, irImage.HeightPixels, PixelFormat.Format8bppIndexed);

    ColorPalette palette = bitmap.Palette;
    for (int i = 0; i < 256; i++)
    {
        palette.Entries[i] = Color.FromArgb(i, i, i);
    }
    bitmap.Palette = palette;

    var rect = new Rectangle(0, 0, bitmap.Width, bitmap.Height);
    var bitmapData = bitmap.LockBits(rect, ImageLockMode.WriteOnly, bitmap.PixelFormat);
    System.Runtime.InteropServices.Marshal.Copy(normalizedIRData, 0, bitmapData.Scan0, normalizedIRData.Length);
    bitmap.UnlockBits(bitmapData);

    bitmap.Save(irname, System.Drawing.Imaging.ImageFormat.Jpeg);
}

void PredictOBB(string currentDirectory, string pythonExePath, K4AdotNet.Sensor.Calibration deviceCalibration, K4AdotNet.Sensor.Image depthImage)
{
    string scriptPredictPath = currentDirectory + @"\predict.py";

    ProcessStartInfo startOBB = new ProcessStartInfo();
    startOBB.FileName = pythonExePath;
    startOBB.Arguments = scriptPredictPath;
    startOBB.UseShellExecute = false;
    startOBB.RedirectStandardOutput = true;
    startOBB.RedirectStandardInput = false;
    startOBB.CreateNoWindow = false;

    Process processPythonOBB = new Process();
    processPythonOBB.StartInfo = startOBB;
    processPythonOBB.Start();

    string output = processPythonOBB.StandardOutput.ReadToEnd();
    processPythonOBB.WaitForExit();

    Console.WriteLine("Données renvoyées par le script Python :");
    Console.WriteLine(output);

    List<PointF> polygonPointsIR = new List<PointF>();

    string pattern = @"Point \d+: \((\d+), (\d+)\)";
    Regex regex = new Regex(pattern);
    MatchCollection matches = regex.Matches(output);

    foreach (Match match in matches)
    {
        if (match.Success)
        {
            float x = float.Parse(match.Groups[1].Value);
            float y = float.Parse(match.Groups[2].Value);
            polygonPointsIR.Add(new PointF(x, y));
        }
    }

    foreach (var point in polygonPointsIR)
    {
        Console.WriteLine($"Point: ({point.X}, {point.Y})");
    }

    foreach (PointF point in polygonPointsIR)
    {
        var point2D = new K4AdotNet.Float2(point.X, point.Y);
        pointsJoints2DPixelDepthOneFrame.Add(new PointF(point2D.X, point2D.Y));
    }
}

void SaveAllMasks(K4AdotNet.Sensor.Calibration deviceCalibration, K4AdotNet.Sensor.Image depthImage, int width_depth, int height_depth, string outputDirectoryPath, List<PointF> pointsJoints2DPixelDepthOneFrame, List<PointF> pointsJoints2DPixelRGBOneFrame, string rgbname)
{
    Bitmap mask = new Bitmap(width_depth, height_depth);
    using (Graphics g = Graphics.FromImage(mask))
    {
        g.Clear(Color.Black);
        Brush brush = new SolidBrush(Color.White);
        if (pointsJoints2DPixelDepthOneFrame.Count > 0)
        {
            g.FillPolygon(brush, pointsJoints2DPixelDepthOneFrame.ToArray());
        }
    }
    string maskPath = $@"{outputDirectoryPath}\mask_depth.png";
    mask.Save(maskPath);

    Bitmap rgbImage_BW = new Bitmap(deviceCalibration.ColorCameraCalibration.ResolutionWidth, deviceCalibration.ColorCameraCalibration.ResolutionHeight, PixelFormat.Format32bppArgb);
    using (Graphics g = Graphics.FromImage(rgbImage_BW))
    {
        g.Clear(Color.Black);
        Brush brush = new SolidBrush(Color.Red);
        if (pointsJoints2DPixelRGBOneFrame.Count > 0)
        {
            Console.WriteLine("Début du dessin du polygone sur la RGB ...");
            g.FillPolygon(brush, pointsJoints2DPixelRGBOneFrame.ToArray());
        }
    }
    string maskRGBPath = $@"{outputDirectoryPath}\RGB_mask_WB.png";
    rgbImage_BW.Save(maskRGBPath);

    byte[] byteArray = new byte[rgbImage_BW.Size.Width * rgbImage_BW.Size.Height * 4];
    BitmapData data = rgbImage_BW.LockBits(new Rectangle(0, 0, rgbImage_BW.Width, rgbImage_BW.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
    Marshal.Copy(data.Scan0, byteArray, 0, byteArray.Length);
    rgbImage_BW.UnlockBits(data);

    Console.WriteLine($"Taille du tableau d'octets : {byteArray.Length}");
    try
    {
        int width_RGB = deviceCalibration.ColorCameraCalibration.ResolutionWidth;
        int height_RGB = deviceCalibration.ColorCameraCalibration.ResolutionHeight;

        K4AdotNet.Sensor.Image image = K4AdotNet.Sensor.Image.CreateFromArray(
            byteArray,
            K4AdotNet.Sensor.ImageFormat.ColorBgra32,
            width_RGB,
            height_RGB
        );
        Console.WriteLine("Image créée avec succès !");

        byte[] bytes = new byte[width_depth * 4 * height_depth];
        var transformation = new K4AdotNet.Sensor.Transformation(deviceCalibration);
        K4AdotNet.Sensor.Image imageTransformed = K4AdotNet.Sensor.Image.CreateFromArray(
            bytes,
            K4AdotNet.Sensor.ImageFormat.ColorBgra32,
            width_depth,
            height_depth
        );
        transformation.ColorImageToDepthCamera(depthImage, image, imageTransformed);

        Console.WriteLine($"Taille du image transformée : {imageTransformed.SizeBytes}");
        byte[] colorDataTransformed = new byte[imageTransformed.SizeBytes];
        imageTransformed.CopyTo(dst: colorDataTransformed);

        Bitmap bitmapTransformed = new Bitmap(width_depth, height_depth, PixelFormat.Format32bppArgb);
        BitmapData dataTransformed = bitmapTransformed.LockBits(new Rectangle(0, 0, width_depth, height_depth), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        Marshal.Copy(colorDataTransformed, 0, dataTransformed.Scan0, colorDataTransformed.Length);
        bitmapTransformed.UnlockBits(dataTransformed);

        string rgbTransformedPath = $@"{outputDirectoryPath}\RGB_transformed.png";
        bitmapTransformed.Save(rgbTransformedPath);
        Console.WriteLine("Image transformée sauvegardée avec succès !");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"Erreur : {ex.Message}");
    }

    // --- DESSIN DU CONTOUR ROUGE ROI UNIQUEMENT ---
    Bitmap rgbImage = new(rgbname);
    using (Graphics g = Graphics.FromImage(rgbImage))
    {
        using (Pen pen = new Pen(Color.Red, 4))
        {
            if (pointsJoints2DPixelRGBOneFrame.Count > 0)
            {
                g.DrawPolygon(pen, pointsJoints2DPixelRGBOneFrame.ToArray());
            }
        }
    }
    rgbImage.Save($@"{outputDirectoryPath}\RGB_mask.jpg");
    Console.WriteLine("Sélection de la région d'intérêt finalisée");
    Console.WriteLine("Démarrage de l'acquisition ...");
}

void SurfaceDepthsPixels(List<int> pixelsIndexMask, List<double> surfaceList, K4AdotNet.Sensor.Calibration deviceCalibration, short[] depthData, int width_depth, int height_depth)
{
    for (int i = 0; i < pixelsIndexMask.Count; i++)
    {
        double pixel_k_profondeur = depthData[pixelsIndexMask[i]];
        int x = pixelsIndexMask[i] % width_depth;
        int y = pixelsIndexMask[i] / width_depth;

        int x_gauche = x - 1;
        int x_droite = x + 1;
        int y_haut = y - 1;
        int y_bas = y + 1;

        var point2D_gauche = new K4AdotNet.Float2(x_gauche, y);
        var point2D_droite = new K4AdotNet.Float2(x_droite, y);
        var point2D_haut = new K4AdotNet.Float2(x, y_haut);
        var point2D_bas = new K4AdotNet.Float2(x, y_bas);

        var Joint3D_gauche = deviceCalibration.Convert2DTo3D(point2D_gauche, (float)pixel_k_profondeur, K4AdotNet.Sensor.CalibrationGeometry.Depth, K4AdotNet.Sensor.CalibrationGeometry.Depth);
        var Joint3D_droite = deviceCalibration.Convert2DTo3D(point2D_droite, (float)pixel_k_profondeur, K4AdotNet.Sensor.CalibrationGeometry.Depth, K4AdotNet.Sensor.CalibrationGeometry.Depth);
        var Joint3D_haut = deviceCalibration.Convert2DTo3D(point2D_haut, (float)pixel_k_profondeur, K4AdotNet.Sensor.CalibrationGeometry.Depth, K4AdotNet.Sensor.CalibrationGeometry.Depth);
        var Joint3D_bas = deviceCalibration.Convert2DTo3D(point2D_bas, (float)pixel_k_profondeur, K4AdotNet.Sensor.CalibrationGeometry.Depth, K4AdotNet.Sensor.CalibrationGeometry.Depth);

        double distance_x = Math.Abs(Joint3D_gauche.Value.X - Joint3D_droite.Value.X);
        double distance_y = Math.Abs(Joint3D_haut.Value.Y - Joint3D_bas.Value.Y);

        double taille_x = distance_x / 2;
        double taille_y = distance_y / 2;

        if (i == 0)
        {
            Console.WriteLine($"Taille du pixel {i} : {taille_x} x {taille_y}");
        }

        double surface = taille_x * taille_y;
        surfaceList.Add(surface);
    }
}