from ultralytics import YOLO

# Load a model
model_path = ('./model_IR.pt')
model = YOLO(model_path)  # load a custom model


# Predict with the model
image_path = "./Output/IR4OBB.jpg"

#results = model(0, show=True) # Use 0 instead of image_path to predict from webcam

results = model(image_path, save=True, save_txt=True, exist_ok=True, conf=0.6, device='cuda')

for result in results :
    obb_tensor=result.obb.xyxyxyxy

obb_numpy = obb_tensor.cpu().detach().numpy()
# Extraire les coordonnées des points
x1, y1 = obb_numpy[0][0]  # Premier point (x1, y1)
x2, y2 = obb_numpy[0][1]  # Deuxième point (x2, y2)
x3, y3 = obb_numpy[0][2]  # Troisième point (x3, y3)
x4, y4 = obb_numpy[0][3]  # Quatrième point (x4, y4)

# Arrondir les coordonnées à l'entier le plus proche
x1, y1 = round(x1), round(y1)
x2, y2 = round(x2), round(y2)
x3, y3 = round(x3), round(y3)
x4, y4 = round(x4), round(y4)

# Afficher les coordonnées
print(f"Point 1: ({x1}, {y1})")
print(f"Point 2: ({x2}, {y2})")
print(f"Point 3: ({x3}, {y3})")
print(f"Point 4: ({x4}, {y4})")