execute unless entity @s[type=minecraft:player] run return 0
execute unless dimension minecampus_mensa:study run return run tellraw @s {"text":"You are already outside the Mensa preview.","color":"yellow"}
execute unless score @s mc_mback matches 1 run return run tellraw @s {"text":"No campus return point is saved. Use /execute in minecraft:overworld run tp @s 0 90 0 if you entered this dimension manually.","color":"yellow"}
execute store result storage minecampus_mensa:travel return.x double 0.01 run scoreboard players get @s mc_mx
execute store result storage minecampus_mensa:travel return.y double 0.01 run scoreboard players get @s mc_my
execute store result storage minecampus_mensa:travel return.z double 0.01 run scoreboard players get @s mc_mz
execute store result storage minecampus_mensa:travel return.yaw double 0.01 run scoreboard players get @s mc_mrot
execute store result storage minecampus_mensa:travel return.pitch double 0.01 run scoreboard players get @s mc_mpitch
function minecampus_mensa:return_position with storage minecampus_mensa:travel return
