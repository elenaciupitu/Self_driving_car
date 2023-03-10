# -*- coding: utf-8 -*-
"""Final_Self_driving_car.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/10IZLGYWCR1yL8YpUf3hjlh8EApmkwQj6

## **SELF DRIVING CAR PROJECT**

# Import dataset & libraries
"""

from google.colab import drive
drive.mount('/content/drive', force_remount=True)

# !unzip /content/drive/MyDrive/Colab\ Notebooks/Self_Driving_Car_Project/Self_Driving_Car.zip -d /content/drive/MyDrive/Colab\ Notebooks/Self_Driving_Car_Project

!pip install -U torch torchvision
!pip install git+https://github.com/facebookresearch/fvcore.git
!git clone https://github.com/facebookresearch/detectron2 detectron2_repo
!pip install -e detectron2_repo

import os
import time
import math
import json
import random
from collections import Counter
import matplotlib.pyplot as plt
from google.colab.patches import cv2_imshow

import numpy as np
import pandas as pd
import cv2
import seaborn as sns

from detectron2.data.datasets import register_coco_instances
from detectron2.data import MetadataCatalog
from detectron2.data import DatasetCatalog
from detectron2.utils.visualizer import Visualizer
from detectron2.engine import DefaultTrainer
from detectron2.config import get_cfg
from detectron2.engine import DefaultPredictor
from detectron2.utils.visualizer import ColorMode
from detectron2.evaluation import COCOEvaluator, inference_on_dataset
from detectron2.data import build_detection_test_loader

"""## Definirea path-urilor/ variabilelor cod"""

json_annotation_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/export/_annotations.coco.json"
json_cleaned_annotation_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/export/_annotations_no_cars.coco.json"
image_directory = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/export/"
model_config = "./detectron2_repo/configs/COCO-Detection/faster_rcnn_R_50_FPN_1x.yaml"
model_zoo_weigths = "detectron2://COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x/137849600/model_final_f10217.pkl"
# output_dir = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output_50" # de schimbat de la experiment la experiment
output_dir = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output" # in functie de ce model testez trebuie rulat sau nu
output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-170956-002641"
video_path = '/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC/'
device = "cpu" # modify this to "cuda" if GPU is available

"""# Exploratory Data Analisys

### Reading the JSON file
"""

# Opening JSON file
f = open(json_annotation_path)

# returns JSON object as a dictionary
data = json.load(f)

"""### Grouping the dictionaries"""

categories = data['categories']
images = data['images']
annotations = data['annotations']

# Create a shortcut dictionary with the ID of all categories 
id_2_cat = {}
for element in categories:
    id_2_cat[element['id']] = element['name']

d = {'image_id': [], "category_id": [], 'object_id': [], 'x': [], 'y': [], 'w': [], 'h': [], 'area': [], 'aspect': []}

for annotation in annotations:
    d['image_id'].append(annotation['image_id'])
    d['category_id'].append(annotation['category_id'])
    d['object_id'].append(annotation['id'])
    d['x'].append(annotation['bbox'][0])
    d['y'].append(annotation['bbox'][1])
    d['w'].append(annotation['bbox'][2])
    d['h'].append(annotation['bbox'][3])
    d['area'].append(int(math.sqrt(annotation['bbox'][2] * annotation['bbox'][3])))
    d['aspect'].append(annotation['bbox'][2]/annotation['bbox'][3])

"""## Distribution of object classes"""

# Grouping the dictionaries

df_objects = pd.DataFrame(data=d)
groups = df_objects.groupby(by='category_id')

x = []
heights = []

for key, group in groups:
    x.append(id_2_cat[key])
    heights.append(group.shape[0])

plt.rcParams['figure.figsize'] = (15, 10)

plt.bar(x, heights)
_ = plt.xticks(range(len(x)), x, rotation=90)
plt.title('Distribution of the objects detected')
plt.xlabel('Objects detected')
plt.ylabel('Count')
plt.show

"""## The distribution of the areas of the objects

"""

_ = plt.hist(df_objects['area'], bins=50)
plt.show()

"""## Appearance of the objects W/H"""

_ = plt.hist(df_objects['aspect'], bins=50)
plt.show()

"""## Conclusions

*   We can observe that we have a lot of cars. The dataset is not balanced. We have to take care on clases with few elements. We must eather increase the number of objects with few elements or reduce the objects with cars in them.
*   From the two histograms we can see the dimension of the objects.
*   The preset anchors are 1:2, 1:1, 2:1 and we can see from the histogram with the appearance of the objects that we can include the objects in the dataset with the preset anchors. Most objects have the appearance between the values ??????0 and 2)

## Removing overlapping bounding boxes

### Grouping the dictionaries and Checking the bboxes
"""

df_images = pd.DataFrame(data=d)
groups_img = df_images.groupby(by='image_id')

new_annotations = [] # here we will put the id's of the rows that we are keeping

for image_id, group in groups_img:
    repeted_boxes = [] #  here we will put the bboxes witch are repeating at least two times
    for ind in group.index:
        contor = 0
        # bboxes elements
        x = group['x'][ind]
        y = group['y'][ind]
        w = group['w'][ind]
        h = group['h'][ind]

        for ind2 in group.index:
            x2 = group['x'][ind2]
            y2 = group['y'][ind2]
            w2 = group['w'][ind2]
            h2 = group['h'][ind2]

            if ind == ind2:
                continue
            if (x == x2) and (y == y2) and (w == w2) and (h == h2):
                print("Am gasit")
                contor += 1 
        if contor > 0:
            if ([x, y, w, h] in repeted_boxes) == False: # if x, y, w, h in repeted_boxes == False --> (we check if we have met before a bbox)
                new_annotations.append(ind)
                repeted_boxes.append([x, y, w, h])
        if contor == 0:
            new_annotations.append(ind) # we put only the indexes

"""### Writting the JSON file with only the good id's

We want to take from annotations only the good id's (new_annotations) so that we can restore the JSON file.
"""

# we take the good id's from annotation:
new_object = [annotation for annotation in  data["annotations"] if annotation['id'] in new_annotations]
data["annotations"] = new_object

# creating a new json file
with open(json_annotation_path, "w") as outfile:
    json.dump(data, outfile, indent=4)

# reading the new json file
# with open(json_annotation_path, "r") as fhandle:
#     data_altered = json.load(fhandle)

"""## Preparing for fine-tuning

*   We will train the model on many epochs, including with wrong bboxes.
*   We will have to remove from the images with only cars because are too many.
*   We will remove the wrong bboxes calculating the IOU.
*   We will retrain the model on the smaller and cleaned data set.

### Searching for images containg only cars
"""

# First step: we check image_id to be unic
# Second step: we check if it has category_id 2

df_objects = pd.DataFrame(data=d)
groups = df_objects.groupby(by='image_id')

cars = [] # images containing only cars

for image_id, group in groups:
    if group[group['category_id'] != 2].shape[0] == 0:
        cars.append(image_id)

"""### Counting the cars from images containing only cars (cars list) """

# We have to find out how many cars are in the 10424 images with only cars.
# Answer: how many times image_id from cars can be found in annotations

# First method:
# counter = 0

# for i in data['annotations']:
#     if i['image_id'] in cars:
#         counter +=1
# print(counter)

# Second method:
print(df_objects[df_objects["image_id"].isin(cars) == True].shape[0]) # using the dataframe we created before

"""### Distribution of cars area from the 10424 images that contain only cars"""

aria = []

for i in data["annotations"]:
  if i["category_id"] == 2:
    aria.append(math.sqrt(i["area"]))

plt.figure(figsize=(15, 10))
plt.hist(aria, bins=50)

"""### Distribution of all cars from the entire dataset"""

aria = []

for i in data["annotations"]:
  if i["image_id"] in cars:
    aria.append(math.sqrt(i["area"]))

plt.figure(figsize=(15, 10))
plt.hist(aria, bins=50)

"""### Distribution of cars from the 10424 images that contain only cars"""

df_only_cars = df_objects[df_objects["image_id"].isin(cars) == True]

sns.histplot(data=df_only_cars, x ="area")

"""### Distribution of all cars """

sns.histplot(data=df_objects, x ="area")

"""### Creating a new JSON file in which we will keep only the images with several objects

We will remove from JSON annotations.coco all the entries that have the id in cars. We will save a new coco JSON type with that entries.
"""

no_cars = [annotation for annotation in data["annotations"] if (annotation['image_id'] in cars) == False]
data['annotations'] = no_cars

with open(json_cleaned_annotation_path, "w") as outfile:
    json.dump(data, outfile, indent=4)

"""### The distribution of areas of the car objects in the new JSON and the comparison with the original distribution  """

# Plot with cars distribution from the new JSON file

sns.histplot(data=df_objects, x ="area")

aria = []

for i in data["annotations"]:
    if i["category_id"] == 2:
        aria.append(math.sqrt(i["area"]))

plt.figure(figsize=(15, 10))
plt.hist(aria, bins=50)

"""# Train Detectron2 model RESNET 50

Now, let's fine-tune a COCO-pretrained R50-FPN Mask R-CNN model on the self driving cars dataset.
"""

register_coco_instances("self_cars_51", {}, "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/export/_annotations.coco.json", "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/export")
# Each dataset is associated with some metadata
cars_metadata = MetadataCatalog.get("self_cars_51")
dataset_dicts = DatasetCatalog.get("self_cars_51")

"""### Run a pre-trained detectron2 model"""

# To verify the data loading is correct, let???s visualize the annotations of randomly selected samples in the dataset:

for d in random.sample(dataset_dicts, 10):
# sample() method returns a list with a randomly selection of a specified number of items from a sequnce.
    img = cv2.imread(d["file_name"])
    visualizer = Visualizer(img[:, :, ::-1], metadata=cars_metadata, scale=2)
    vis = visualizer.draw_dataset_dict(d)
    cv2_imshow(vis.get_image()[:, :, ::-1])

"""### Train the model with RESNET 50

"""

# cfg = get_cfg()
# cfg.merge_from_file(
#     "/content/detectron2_repo/configs/COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml"
# )
# cfg.DATASETS.TRAIN = ("self_cars_51",)
# cfg.DATASETS.TEST = ()  # no metrics implemented for this dataset
# cfg.DATALOADER.NUM_WORKERS = 2
# cfg.MODEL.WEIGHTS = "detectron2://COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x/137849600/model_final_f10217.pkl"  
# cfg.SOLVER.IMS_PER_BATCH = 2
# cfg.SOLVER.BASE_LR = 0.0002
# cfg.SOLVER.MAX_ITER = (
#     50000
# )  # 300 iterations seems good enough, but you can certainly train longer
# cfg.SOLVER.CHECKPOINT_PERIOD = 5000
# # cfg.SOLVER.CHECKPOINT_PERIOD = 1000
# cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = (
#     128
# )  # faster, and good enough for this toy dataset
# cfg.MODEL.ROI_HEADS.NUM_CLASSES = 11  # 3 classes (data, fig, hazelnut)

# cfg.OUTPUT_DIR = output_dir
# os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
# trainer = DefaultTrainer(cfg)
# trainer.resume_or_load(resume=True)
# trainer.train()

"""#### Training curves"""

# Commented out IPython magic to ensure Python compatibility.
# Look at training curves in tensorboard:
# %load_ext tensorboard
# %tensorboard --logdir "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output"

"""### Make a prediction RESNET 50"""

cfg = get_cfg()
cfg.merge_from_file(
    "/content/detectron2_repo/configs/COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml")
cfg.OUTPUT_DIR = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output_50"
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 11
cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5   # set the testing threshold for this model
cfg.DATASETS.TEST = ("self_cars_51", )
predictor = DefaultPredictor(cfg)

for d in random.sample(dataset_dicts, 10):
# sample() method returns a list with a randomly selection of a specified number of items from a sequnce.
    img = cv2.imread(d["file_name"])
    visualizer = Visualizer(img[:, :, ::-1], metadata=cars_metadata, scale=2) 
    vis = visualizer.draw_dataset_dict(d)
    cv2_imshow(vis.get_image()[:, :, ::-1])

"""## Prediction on a real set of images  """

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-170956-002641"

# for d in random.sample(dataset_dicts, 20):    #### sa parcurgem folderul doar pana la primele 20 de imagini
#     im = 
# incarcarea modelului

output_path2 = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output_50"

cfg = get_cfg()
cfg.merge_from_file(
    "./detectron2_repo/configs/COCO-Detection/faster_rcnn_R_50_FPN_1x.yaml"
)


cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = (128)
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 11  # 11 clase ("obstacles", clasa 0, este super clasa care le contine pe restul de 11, nu se pune)

cfg.OUTPUT_DIR = output_path2
cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5
cfg.DATASETS.TEST = ("cars", )
cfg.MODEL.DEVICE = "cpu"
predictor = DefaultPredictor(cfg)

"""#### Prediction - day light"""

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-170956-002641"

numarator = 1
for file in os.listdir(output_path):
  if numarator <= 20:
    im = cv2.imread(os.path.join(output_path, file))
    print(file)
    outputs = predictor(im)
    v = Visualizer(im[:, :, ::-1],
                   metadata=cars_metadata, 
                   scale=0.8, 
                  #  instance_mode=ColorMode.IMAGE_BW   # remove the colors of unsegmented pixels
    )
    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
    cv2_imshow(v.get_image()[:, :, ::-1])
    numarator += 1
  else:
    break

"""#### Prediction - night light no.1"""

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-191709-002645"

# for d in random.sample(dataset_dicts, 3):    #### sa parcurgem folderul doar pana la primele 20 de imagini
#     im = cv2.imread(d["file_name"])          #### 

numarator = 1
for file in os.listdir(output_path):
  if numarator <= 20:
    im = cv2.imread(os.path.join(output_path, file))
    print(file)
    outputs = predictor(im)
    v = Visualizer(im[:, :, ::-1],
                   metadata=cars_metadata, 
                   scale=0.8, 
                  #  instance_mode=ColorMode.IMAGE_BW   # remove the colors of unsegmented pixels
    )
    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
    cv2_imshow(v.get_image()[:, :, ::-1])
    numarator += 1
  else:
    break

"""#### Prediction - night light no.2  """

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-192019-002646"

# for d in random.sample(dataset_dicts, 3):    #### sa parcurgem folderul doar pana la primele 20 de imagini
#     im = cv2.imread(d["file_name"])          #### 

numarator = 1
for file in os.listdir(output_path):
  if numarator <= 20:
    im = cv2.imread(os.path.join(output_path, file))
    print(file)
    outputs = predictor(im)
    v = Visualizer(im[:, :, ::-1],
                   metadata=cars_metadata, 
                   scale=0.8, 
                  #  instance_mode=ColorMode.IMAGE_BW   # remove the colors of unsegmented pixels
    )
    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
    cv2_imshow(v.get_image()[:, :, ::-1])
    numarator += 1
  else:
    break

"""# Train Detectron2 model RESNET 101

## Run a pre-trained detectron2 model
"""

register_coco_instances("self_cars", {}, "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/export/_annotations.coco.json", "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/export")
# Each dataset is associated with some metadata
cars_metadata = MetadataCatalog.get("self_cars")
dataset_dicts = DatasetCatalog.get("self_cars")

# To verify the data loading is correct, let???s visualize the annotations of randomly selected samples in the dataset:

for d in random.sample(dataset_dicts, 5):
# sample() method returns a list with a randomly selection of a specified number of items from a sequnce.
    img = cv2.imread(d["file_name"])
    visualizer = Visualizer(img[:, :, ::-1], metadata=cars_metadata, scale=2)
    vis = visualizer.draw_dataset_dict(d)
    cv2_imshow(vis.get_image()[:, :, ::-1])

"""### Train"""

# cfg = get_cfg()
# cfg.merge_from_file("/content/detectron2_repo/configs/COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml")
# cfg.DATASETS.TRAIN = ("self_cars",)
# cfg.DATASETS.TEST = ()  # no metrics implemented for this dataset
# cfg.DATALOADER.NUM_WORKERS = 2
# cfg.MODEL.WEIGHTS = "detectron2://ImageNetPretrained/FAIR/X-101-32x8d.pkl" 
# cfg.SOLVER.IMS_PER_BATCH = 2
# cfg.SOLVER.BASE_LR = 0.0002
# cfg.SOLVER.MAX_ITER = 50000  # 300 iterations seems good enough, but you can certainly train longer
# cfg.SOLVER.CHECKPOINT_PERIOD = 5000
# # cfg.SOLVER.CHECKPOINT_PERIOD = 1000
# cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = 128  # faster, and good enough for this toy dataset
# cfg.MODEL.ROI_HEADS.NUM_CLASSES = 11  # Object este clasa care le include pe toate celelalte

# cfg.OUTPUT_DIR = output_dir
# os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
# trainer = DefaultTrainer(cfg)
# trainer.resume_or_load(resume=True)
# trainer.train()

"""## Inference & evaluation using the trained model"""

# Inference should use the config with parameters that are used in training
# cfg now already contains everything we've set previously. We changed it a little bit for inference:

# output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-170956-002641"
output_path2 = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output"

cfg = get_cfg()
cfg.merge_from_file("/content/detectron2_repo/configs/COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml")

cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = (128)
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 11  # 11 clase ("obstacles", clasa 0, este super clasa care le contine pe restul de 11, nu se pune)

cfg.OUTPUT_DIR = output_path2
cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth") # path to the model we just trained
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5 # de la ce confidenta in sus afiseaza bbox-uri
cfg.DATASETS.TEST = ("cars", )
cfg.MODEL.DEVICE = "cuda"
predictor = DefaultPredictor(cfg)

from detectron2.evaluation import COCOEvaluator, inference_on_dataset
from detectron2.data import build_detection_test_loader
evaluator = COCOEvaluator("self_cars", output_dir=output_path2)
val_loader = build_detection_test_loader(cfg, "self_cars")
print(inference_on_dataset(predictor.model, val_loader, evaluator))

"""## Prediction - RESNET 101

"""

cfg = get_cfg()
cfg.merge_from_file("/content/detectron2_repo/configs/COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml")
cfg.OUTPUT_DIR = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output"
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 11
cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5   # set the testing threshold for this model
cfg.DATASETS.TEST = ("self_cars", )
predictor = DefaultPredictor(cfg)

#  We randomly select several samples to visualize the prediction results.

for d in random.sample(dataset_dicts, 10):
    im = cv2.imread(d["file_name"])
    outputs = predictor(im)
    v = Visualizer(im[:, :, ::-1],
                   metadata=cars_metadata, 
                   scale=2, 
                  #  instance_mode=ColorMode.IMAGE_BW   # remove the colors of unsegmented pixels
    )
    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
    cv2_imshow(v.get_image()[:, :, ::-1])

# inference speed

times = []
for i in range(20):
    start_time = time.time()
    outputs = predictor(im)
    delta = time.time() - start_time
    times.append(delta)
mean_delta = np.array(times).mean()
fps = 1 / mean_delta
print("Average(sec):{:.2f},fps:{:.2f}".format(mean_delta, fps))

"""#### Prediction - day light"""

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-162802-002627"
output_path1011 = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output"

cfg = get_cfg()
cfg.merge_from_file("/content/detectron2_repo/configs/COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml")

cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = (128)
cfg.MODEL.ROI_HEADS.NUM_CLASSES = 11  # 11 clase ("obstacles", clasa 0, este super clasa care le contine pe restul de 11, nu se pune)

cfg.OUTPUT_DIR = output_path1011
cfg.MODEL.WEIGHTS = os.path.join(cfg.OUTPUT_DIR, "model_final.pth")
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5
cfg.DATASETS.TEST = ("cars", )
cfg.MODEL.DEVICE = "cpu"
predictor = DefaultPredictor(cfg)

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-141551-002609"

numarator = 1
for file in os.listdir(output_path):
  if numarator <= 20: #### sa parcurgem folderul doar pana la primele 20 de imagini
    im = cv2.imread(os.path.join(output_path, file))
    print(file)
    outputs = predictor(im)
    v = Visualizer(im[:, :, ::-1],
                   metadata=cars_metadata, 
                   scale=0.8, 
                  #  instance_mode=ColorMode.IMAGE_BW   # remove the colors of unsegmented pixels
    )
    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
    cv2_imshow(v.get_image()[:, :, ::-1])
    numarator += 1
  else:
    break

"""#### Prediction - night light no.1"""

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-191409-002644"

# for d in random.sample(dataset_dicts, 3):    #### sa parcurgem folderul doar pana la primele 20 de imagini
#     im = cv2.imread(d["file_name"])          #### 

numarator = 1
for file in os.listdir(output_path):
  if numarator <= 20:
    im = cv2.imread(os.path.join(output_path, file))
    print(file)
    outputs = predictor(im)
    v = Visualizer(im[:, :, ::-1],
                   metadata=cars_metadata, 
                   scale=0.8, 
                  #  instance_mode=ColorMode.IMAGE_BW   # remove the colors of unsegmented pixels
    )
    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
    cv2_imshow(v.get_image()[:, :, ::-1])
    numarator += 1
  else:
    break

"""#### Prediction - night light no.2  """

output_path = "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/POZE_TRAFIC/NO20221005-192019-002646"

# for d in random.sample(dataset_dicts, 3):    #### sa parcurgem folderul doar pana la primele 20 de imagini
#     im = cv2.imread(d["file_name"])          #### 

numarator = 1
for file in os.listdir(output_path):
  if numarator <= 20:
    im = cv2.imread(os.path.join(output_path, file))
    print(file)
    outputs = predictor(im)
    v = Visualizer(im[:, :, ::-1],
                   metadata=cars_metadata, 
                   scale=0.8, 
                  #  instance_mode=ColorMode.IMAGE_BW   # remove the colors of unsegmented pixels
    )
    v = v.draw_instance_predictions(outputs["instances"].to("cpu"))
    cv2_imshow(v.get_image()[:, :, ::-1])
    numarator += 1
  else:
    break

"""## Converting a video in images"""

# !pip install opencv-python

output_path = '/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC_INFERENCE/'

if os.path.isdir(output_path) == False:
  os.makedirs(output_path)

vidcap = cv2.VideoCapture('/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC/NO20221005-155752-002617.MP4')
success, image = vidcap.read()
count = 1
i = 0
while success:
  if i % 5 == 0:
    cv2.imwrite(os.path.join(output_path, "image_%d.jpg" % count), image)
  i += 1    
  success, image = vidcap.read()
  print('Saved image ', count)
  count += 1

"""## Run panoptic segmentation on a video"""

# This is the video we're going to process
from IPython.display import YouTubeVideo, display
video = YouTubeVideo("ll8TgCZ0plk", width=500)
display(video)

# Install dependencies, download the video, and crop 5 seconds for processing
!pip install youtube-dl
!youtube-dl https://www.youtube.com/watch?v=ll8TgCZ0plk -f 22 -o video.mp4
!ffmpeg -i video.mp4 -t 00:00:06 -c:v copy video-clip.mp4

# Commented out IPython magic to ensure Python compatibility.
# Run frame-by-frame inference demo on this video (takes 3-4 minutes) with the "demo.py" tool we provided in the repo.
!git clone https://github.com/facebookresearch/detectron2
# Note: this is currently BROKEN due to missing codec. See https://github.com/facebookresearch/detectron2/issues/2901 for workaround.
# %run detectron2/demo/demo.py --config-file detectron2/configs/COCO-PanopticSegmentation/panoptic_fpn_R_101_3x.yaml --video-input video-clip.mp4 --confidence-threshold 0.6 --output video-output.mkv \
  --opts MODEL.WEIGHTS detectron2://COCO-PanopticSegmentation/panoptic_fpn_R_101_3x/139514519/model_final_cafdb1.pkl

# Download the results
from google.colab import files
files.download('video-output.mkv')

"""## VIDEO INFERENCE"""

# !pip install opencv-python

output_path = '/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC_INFERENCE/'

if os.path.isdir(output_path) == False:
  os.makedirs(output_path)

vidcap = cv2.VideoCapture('/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC_INFERENCE/Video_trafic.mp4')
success, image = vidcap.read()

# Install dependencies, download the video, and crop 5 seconds for processing
!ffmpeg -i '/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC_INFERENCE/Video_trafic.mp4' -t 00:00:06 -c:v copy "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC_INFERENCE/Video-trafic-inference.mp4"

# Commented out IPython magic to ensure Python compatibility.
# Run frame-by-frame inference demo on this video (takes 3-4 minutes) with the "demo.py" tool we provided in the repo.
!git clone https://github.com/facebookresearch/detectron2
# Note: this is currently BROKEN due to missing codec. See https://github.com/facebookresearch/detectron2/issues/2901 for workaround.
# %run detectron2/demo/demo.py --config-file /content/detectron2_repo/configs/COCO-Detection/faster_rcnn_R_101_FPN_3x.yaml --video-input '/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/VIDEO_TRAFIC_INFERENCE/Video_trafic.mp4' --confidence-threshold 0.5 --output video-output-inf.mkv \
  --opts MODEL.WEIGHTS https://dl.fbaipublicfiles.com/detectron2/COCO-Detection/retinanet_R_101_FPN_3x/138363263/model_final_59f53c.pkl

# Download the results
from google.colab import files
files.download('video-output-inf.mkv')

"""# Learning rates"""

# Commented out IPython magic to ensure Python compatibility.
# %load_ext tensorboard
# %tensorboard --logdir "/content/drive/MyDrive/Colab Notebooks/Self_Driving_Car_Project/output"

