execute in minecampus_mensa:study store success score #built mc_mensa run place template minecampus_mensa:mensa -10 64 -10
execute in minecampus_mensa:study run forceload remove -16 -16 96 96
execute if score #built mc_mensa matches 1 in minecampus_mensa:study run tellraw @a[distance=..200] {"text":"Mensa ready. Doors open with pressure plates. Food barrels and smokers are usable. /function minecampus_mensa:back returns you to campus.","color":"green"}
