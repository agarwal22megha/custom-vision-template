import json
import logging
import os

import azure.functions as func
import requests

AZURE_COG_PREDICTION_KEY = os.getenv('AZURE_COG_PREDICTION_KEY')

POTHOLE_LOCATION_URL = os.getenv('POTHOLE_LOCATION_URL')
POTHOLE_LOCATION_PROJECT_ID = os.getenv('POTHOLE_LOCATION_PROJECT_ID')
POTHOLE_LOCATION_ITERATION_ID = os.getenv('POTHOLE_LOCATION_ITERATION_ID')

POTHOLE_DETECTION_URL = os.getenv('POTHOLE_DETECTION_URL')
POTHOLE_DETECTION_PROJECT_ID = os.getenv('POTHOLE_DETECTION_PROJECT_ID')
POTHOLE_DETECTION_ITERATION_ID = os.getenv('POTHOLE_DETECTION_ITERATION_ID')


def get_predictions(image_url, project_url, iteration_id):
    querystring = {"iterationId": iteration_id}
    payload = "{\"Url\": \"" + image_url + "\"}"
    headers = {
        'Prediction-Key': AZURE_COG_PREDICTION_KEY,
        'Content-Type': "application/json"
    }
    response = requests.request(
        "POST",
        project_url,
        data=payload,
        headers=headers,
        params=querystring
    )
    predictions = json.loads(response.text)
    logging.info("**********{}".format(predictions['predictions']))
    return predictions['predictions']


def get_most_likely_location(locations,
                             threshold=0.5):
    prediction_probability = 0
    most_likely_location = ""
    for location in locations:
        if location['probability'] > prediction_probability:
            prediction_probability = location['probability']
            if prediction_probability > threshold:
                most_likely_location = location['tagName']
    return most_likely_location


def get_pothole_location(image_url):
    likely_locations = get_predictions(image_url,
                                       POTHOLE_LOCATION_URL,
                                       POTHOLE_LOCATION_ITERATION_ID)
    return get_most_likely_location(likely_locations)


def get_area(bounding_box):
    return bounding_box['width'] * bounding_box['height']


def get_potholes(identified_potholes,
                 threshold=0.5):
    potholes = []
    for pothole in identified_potholes:
        if pothole['probability'] > threshold:
            potholes.append(
                {
                    "area": get_area(pothole['boundingBox']),
                    "tag_id": pothole['tagId']
                }
            )
    return potholes


def get_potholes_details(image_url):
    identified_potholes = get_predictions(
        image_url,
        POTHOLE_DETECTION_URL,
        POTHOLE_DETECTION_ITERATION_ID
    )
    likely_potholes = get_potholes(identified_potholes)
    if likely_potholes:
        number_of_potholes = len(likely_potholes)
        avg_area_of_potholes = (
            sum(pothole['area'] for pothole in likely_potholes) / len(likely_potholes)
        )
        return number_of_potholes, avg_area_of_potholes
    else:
        return 0, 0


def get_potholes_info(image_url):
    logging.info(">>>>>>> Processing image: {}".format(image_url))

    logging.info(">>>>>>> Getting Number of Potholes & Avg area...")
    number_of_potholes, avg_area_of_potholes = get_potholes_details(image_url)
    logging.info(">>>>>>> Number of potholes: {}".format(number_of_potholes))
    logging.info(">>>>>>> Average area of potholes: {}".format(avg_area_of_potholes))

    if number_of_potholes > 0:
        logging.info(">>>>>>> Getting Pothole Location...")
        pothole_location = get_pothole_location(image_url)
        logging.info(">>>>>>> Likely location: {}".format(pothole_location))
    else:
        pothole_location = "Unknown"

    return {
        "number_of_potholes": number_of_potholes,
        "average_area_of_potholes": avg_area_of_potholes,
        "location_of_potholes": pothole_location
    }


def json_response(pothole_info):
    return func.HttpResponse(
        body=json.dumps(pothole_info),
        mimetype="application/json"
    )


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    image_url = req.params.get('image_url')
    if not image_url:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            image_url = req_body.get('image_url')

    if image_url:
        logging.info(">>>>>>> Processing image url: {}".format(image_url))
        return json_response(
            get_potholes_info(
                image_url
            )
        )

    else:
        return func.HttpResponse(
            "Please pass an image_url!!",
            status_code=400
        )
