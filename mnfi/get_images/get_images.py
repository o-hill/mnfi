import io
import json
import multiprocessing
import sys
import zipfile
from glob import glob
from pathlib import Path

import ee
import pandas as pd
import requests
from retry import retry
from tqdm import tqdm


@retry(tries=10, delay=1, backoff=2)
def download_item(item):
    url = item["download_url"]
    directory = item["directory"]

    r = requests.get(url, timeout=10)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(Path(__file__).parent / "images" / directory)


# ee.Authenticate()
ee.Initialize(
    project="ee-surfactant", opt_url="https://earthengine-highvolume.googleapis.com"
)

df = pd.read_csv("MichiganGrid-JustCoordinates.csv")

download_urls = []

michigan_geometry = (
    ee.FeatureCollection("FAO/GAUL/2015/level1")
    .filter(ee.Filter.eq("ADM1_NAME", "Michigan"))
    .first()
    .geometry()
    .transform("EPSG:4326")
)

sentinel_collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(michigan_geometry)
    .filterDate("2022-06-01", "2022-09-30")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 5))
)

dw_collection = (
    ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
    .filterBounds(michigan_geometry)
    .filter(ee.Filter.date("2022-06-01", "2022-09-30"))
)

existing_sentinel_images = set(glob("images/*-sentinel"))
existing_dw_images = set(glob("images/*-dynamic-worlds"))


def get_requests():
    # for each row in the dataframe, get the coordinates and get the download url for the respective image
    ee_requests = []

    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        polygon = ee.Geometry.Polygon(json.loads(row[".geo"])[0])

        if f"images/{index}-sentinel" not in existing_sentinel_images:
            sentinel_image = (
                sentinel_collection.filterBounds(polygon)
                .select("B2", "B3", "B4", "B8")
                .mosaic()
                .clip(polygon)
            )

            ee_requests.append(
                {
                    "request": {
                        "name": f"{index}-sentinel",
                        "image": sentinel_image,
                        "region": polygon,
                        "filePerBand": "false",
                        "crs": "EPSG:4326",
                        "scale": 10,
                    },
                    "directory": f"{index}-sentinel",
                    "type": "sentinel",
                }
            )

        if f"images/{index}-dynamic-worlds" not in existing_dw_images:
            dynamic_worlds = dw_collection.filterBounds(polygon).mosaic().clip(polygon)
            ee_requests.append(
                {
                    "request": {
                        "name": f"{index}-dynamic-worlds",
                        "image": dynamic_worlds,
                        "region": polygon,
                        "filePerBand": "false",
                        "crs": "EPSG:4326",
                    },
                    "directory": f"{index}-dynamic-worlds",
                    "type": "dw",
                }
            )

        if len(ee_requests) >= 200000:
            break

    return ee_requests


def get_result(request):
    image = request["request"]["image"]

    item = {
        "download_url": image.getDownloadURL(request["request"]),
        "directory": request["directory"],
    }

    try:
        download_item(item)
    except Exception as e:
        pass


if __name__ == "__main__":
    ee_requests = get_requests()
    with multiprocessing.Pool(processes=25) as pool:
        for _ in tqdm(
            pool.imap_unordered(get_result, ee_requests, chunksize=25),
            total=len(ee_requests),
        ):
            pass
