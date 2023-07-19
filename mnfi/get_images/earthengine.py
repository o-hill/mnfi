import ee
import ee.mapclient
import geemap.geemap as geemap

# ee.Authenticate()
ee.Initialize(project="ee-surfactant")

cdl = (
    ee.ImageCollection("USDA/NASS/CDL")
    .filter(ee.Filter.date("2018-01-01", "2019-12-31"))
    .first()
)

Map = geemap.Map(center=(40, -100), zoom=4)

cropLandcover = cdl.select("cropland")
# print(cropLandcover.getInfo())

Map.addLayer(cropLandcover, {}, "Crop Landcover")
print(Map)
