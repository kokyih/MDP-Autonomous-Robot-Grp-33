# USAGE
# python build_dataset.py

# import the necessary packages
from pyimagesearch.iou import compute_iou
from pyimagesearch import config
from bs4 import BeautifulSoup
from imutils import paths
import cv2
import os
import pandas as pd

# loop over the output positive and negative directories
# for dirPath in (config.POSITVE_PATH, config.NEGATIVE_PATH):
# 	# if the output directory does not exist yet, create it
# 	if not os.path.exists(dirPath):
# 		os.makedirs(dirPath)

# grab all image paths in the input images directory
imagePaths = list(paths.list_images(config.ORIG_BASE_PATH))

# initialize the total number of positive and negative images we have
# saved to disk so far
totalPositive = 1000
totalNegative = 5700

# loop over the image paths
for (i, imagePath) in enumerate(imagePaths):
	# show a progress report
	print("[INFO] processing image {}/{}...".format(i + 1,
		len(imagePaths)))

	# extract the filename from the file path and use it to derive
	# the path to the XML annotation file
	filename = imagePath.split(os.path.sep)[-1]
	# print(filename)
	annotPath = pd.read_csv(config.ORIG_BASE_PATH+"_labels.csv")
	gtBoxes = []
	filename2 = annotPath['filename'] == filename
	annotPath = annotPath[filename2]
	xMin = int(annotPath['xmin'].values[0])
	yMin = int(annotPath['ymin'].values[0])
	xMax = int(annotPath['xmax'].values[0])
	yMax = int(annotPath['ymax'].values[0])
	w = int(annotPath['width'].values[0])
	h = int(annotPath['height'].values[0])
	image_class = str(annotPath['class'].values[0])
	# outside the boundaries of the image
	xMin = max(0, xMin)
	yMin = max(0, yMin)
	xMax = min(w, xMax)
	yMax = min(h, yMax)

	# update our list of ground-truth bounding boxes
	gtBoxes.append((xMin, yMin, xMax, yMax))

	# load the input image from disk
	image = cv2.imread(imagePath)

	# run selective search on the image and initialize our list of
	# proposed boxes
	ss = cv2.ximgproc.segmentation.createSelectiveSearchSegmentation()
	ss.setBaseImage(image)
	ss.switchToSelectiveSearchFast()
	rects = ss.process()
	proposedRects= []

	# loop over the rectangles generated by selective search
	for (x, y, w, h) in rects:
		# convert our bounding boxes from (x, y, w, h) to (startX,
		# startY, startX, endY)
		proposedRects.append((x, y, x + w, y + h))

	# initialize counters used to count the number of positive and
	# negative ROIs saved thus far
	positiveROIs = 0
	negativeROIs = 0

	# loop over the maximum number of region proposals
	for proposedRect in proposedRects[:config.MAX_PROPOSALS]:
		# unpack the proposed rectangle bounding box
		(propStartX, propStartY, propEndX, propEndY) = proposedRect

		# loop over the ground-truth bounding boxes
		for gtBox in gtBoxes:
			# compute the intersection over union between the two
			# boxes and unpack the ground-truth bounding box
			iou = compute_iou(gtBox, proposedRect)
			(gtStartX, gtStartY, gtEndX, gtEndY) = gtBox

			# initialize the ROI and output path
			roi = None
			outputPath = None

			# check to see if the IOU is greater than 70% *and* that
			# we have not hit our positive count limit
			if iou > 0.7 and positiveROIs <= config.MAX_POSITIVE:
				# extract the ROI and then derive the output path to
				# the positive instance
				roi = image[propStartY:propEndY, propStartX:propEndX]
				filename = "{}.png".format(totalPositive)
				positiveOutputPath = os.path.sep.join([config.BASE_PATH, image_class])
				outputPath = os.path.sep.join([positiveOutputPath,
					filename])

				# increment the positive counters
				positiveROIs += 1
				totalPositive += 1

			# determine if the proposed bounding box falls *within*
			# the ground-truth bounding box
			fullOverlap = propStartX >= gtStartX
			fullOverlap = fullOverlap and propStartY >= gtStartY
			fullOverlap = fullOverlap and propEndX <= gtEndX
			fullOverlap = fullOverlap and propEndY <= gtEndY

			# check to see if there is not full overlap *and* the IoU
			# is less than 5% *and* we have not hit our negative
			# count limit
			if not fullOverlap and iou < 0.05 and \
				negativeROIs <= config.MAX_NEGATIVE:
				# extract the ROI and then derive the output path to
				# the negative instance
				roi = image[propStartY:propEndY, propStartX:propEndX]
				filename = "{}.png".format(totalNegative)
				outputPath = os.path.sep.join([config.NEGATIVE_PATH,
					filename])

				# increment the negative counters
				negativeROIs += 1
				totalNegative += 1

			# check to see if both the ROI and output path are valid
			if roi is not None and outputPath is not None:
				# resize the ROI to the input dimensions of the CNN
				# that we'll be fine-tuning, then write the ROI to
				# disk
				roi = cv2.resize(roi, config.INPUT_DIMS,
					interpolation=cv2.INTER_CUBIC)
				cv2.imwrite(outputPath, roi)
