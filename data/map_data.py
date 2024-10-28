# DemonFF - Blender scripts to edit basic GTA formats to work in conjunction with SAMP/open.mp
# 2023 - 2024 SpicyBung

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from collections import namedtuple
from ..ops.importer_common import game_version

III_structures = {}
VC_structures = {}
SA_structures = {}

#############
#    IPL    #
#############

# Sources
# https://gtamods.com/wiki/Item_Placement
# https://www.grandtheftwiki.com/Item_Placement
# https://gta.fandom.com/wiki/Item_Placement

# Known missing:
# PATH
# MULT

# INST
# Places objects defined in objs, tobj, anim or tanm into the world
III_structures['inst'] = namedtuple("IPL_INST_3",  "id modelName posX posY posZ scaleX scaleY scaleZ rotX rotY rotZ rotW")
VC_structures['inst'] =  namedtuple("IPL_INST_VC", "id modelName interior posX posY posZ scaleX scaleY scaleZ rotX rotY rotZ rotW")
SA_structures['inst'] =  namedtuple("IPL_INST_SA", "id modelName interior posX posY posZ rotX rotY rotZ rotW lod")

# CULL
# Creates zones with special attributes
III_structures['cull'] = namedtuple("IPL_CULL_3",      "centerX centerY centerZ lowerLeftX lowerLeftY lowerLeftZ upperRightX upperRightY upperRightZ flags wantedLevelDrop")
VC_structures['cull'] =  namedtuple("IPL_CULL_VC",     "centerX centerY centerZ lowerLeftX lowerLeftY lowerLeftZ upperRightX upperRightY upperRightZ flags wantedLevelDrop")
SA_structures['cull_1'] =  namedtuple("IPL_CULL_SA_1", "centerX centerY centerZ unknown1 widthY bottomZ widthX unknown2 topZ flag unknown3")
SA_structures['cull_2'] =  namedtuple("IPL_CULL_SA_2", "centerX centerY centerZ unknown1 widthY bottomZ widthX unknown2 topZ flag Vx Vy Vz cm")

# ZONE
# Creates map, navigation, and info zones
III_structures['zone'] = namedtuple("IPL_ZONE_3",  "name type x1 y1 z1 x2 y2 z2 level")
VC_structures['zone'] =  namedtuple("IPL_ZONE_VC", "name type x1 y1 z1 x2 y2 z2 level")
SA_structures['zone'] =  namedtuple("IPL_ZONE_SA", "name type x1 y1 z1 x2 y2 z2 level")

# GRGE
# Creates a garage
SA_structures['grge'] = namedtuple("IPL_GRGE_SA", "posX posY posZ lineX lineY cubeX cubeY cubeZ doorType garageType name")

# ENEX
# Creates an entrance to an exit
SA_structures['enex'] = namedtuple("IPL_ENEX_SA", "x1 y1 z1 enterAngle sizeX sizeY sizeZ x2 y2 z2 exitAngle targetInterior flags name sky numPedsToSpawn timeOn timeOff")

# PICK
# Creates pickups. This section exists in GTA III, GTA Vice City, and GTA IV, but is only functional in GTA San Andreas
SA_structures['pick'] = namedtuple("IPL_PICK_SA", "id posX posY posZ")

# JUMP
# Creates a unique stunt jump
SA_structures['jump'] = namedtuple("IPL_JUMP_SA", "startLowerX startLowerY startLowerZ startUpperX startUpperY startUpperZ targetLowerX targetLowerY targetLowerZ targetUpperX targetUpperY targetUpperZ cameraX cameraY cameraZ reward")

# AUZO
# This creates an audio if you enter the zone
SA_structures['auzo_1'] = namedtuple("IPL_AUZO_SA_1", "name id switch x y z radius")
SA_structures['auzo_2'] = namedtuple("IPL_AUZO_SA_2", "name id switch x1 y1 z1 x2 y2 z2")

# CARS
# Creates a parked car generator
SA_structures['cars'] = namedtuple("IPL_CARS_SA", "posX posY posZ angle carId primCol secCol forceSpawn alarm doorLock unknown1 unknown2")

# OCCL
# Creates occlusion zones for separated rendering
VC_structures['occl'] = namedtuple("IPL_OCCL_VC", "midX midY bottomZ widthX widthY height rotation")
SA_structures['occl'] = namedtuple("IPL_OCCL_SA", "midX midY bottomZ widthX widthY height rotation")

# TCYC
SA_structures['occl'] = namedtuple("IPL_TCYC_SA", "x1 y1 z1 x2 y2 z2 farClip extraColor extraColorIntensity falloffDist unknown lodDistMult")

#############
#    IDE    #
#############

# Sources
# https://gtamods.com/wiki/Item_Definition
# https://www.grandtheftwiki.com/Item_Definition
# https://gta.fandom.com/wiki/IDE

# Known missing:
# PATH

# OBJS
# Defines simple objects. They can be placed into the world through the inst section of the item placement files.
III_structures['objs_1'] = namedtuple("IDE_OBJS_3_1",  "id modelName txdName drawDistance flags")
III_structures['objs_2'] = namedtuple("IDE_OBJS_3_2",  "id modelName txdName meshCount drawDistance flags")
III_structures['objs_3'] = namedtuple("IDE_OBJS_3_3",  "id modelName txdName meshCount drawDistance1 drawDistance2 flags")
III_structures['objs_4'] = namedtuple("IDE_OBJS_3_4",  "id modelName txdName meshCount drawDistance1 drawDistance2 drawDistance3 flags")

VC_structures['objs_1'] =  namedtuple("IDE_OBJS_VC_1",  "id modelName txdName drawDistance flags")
VC_structures['objs_2'] =  namedtuple("IDE_OBJS_VC_2",  "id modelName txdName meshCount drawDistance flags")
VC_structures['objs_3'] =  namedtuple("IDE_OBJS_VC_3",  "id modelName txdName meshCount drawDistance1 drawDistance2 flags")
VC_structures['objs_4'] =  namedtuple("IDE_OBJS_VC_4",  "id modelName txdName meshCount drawDistance1 drawDistance2 drawDistance3 flags")

SA_structures['objs_1'] =  namedtuple("IDE_OBJS_SA_1",  "id modelName txdName drawDistance flags")
SA_structures['objs_2'] =  namedtuple("IDE_OBJS_SA_2",  "id modelName txdName meshCount drawDistance flags")
SA_structures['objs_3'] =  namedtuple("IDE_OBJS_SA_3",  "id modelName txdName meshCount drawDistance1 drawDistance2 flags")
SA_structures['objs_4'] =  namedtuple("IDE_OBJS_SA_4",  "id modelName txdName meshCount drawDistance1 drawDistance2 drawDistance3 flags")

# TOBJ
# Defines time objects. The section functions similarly to objs but has two additional
# parameters defining the in-game time range the object can get rendered. These objects
# can be placed into the world through the inst section of the item placement files.
III_structures['tobj_1'] = namedtuple("IDE_TOBJ_3_1",  "id modelName txdName drawDistance flags timeOn timeOff")
III_structures['tobj_2'] = namedtuple("IDE_TOBJ_3_2",  "id modelName txdName meshCount drawDistance flags timeOn timeOff")
III_structures['tobj_3'] = namedtuple("IDE_TOBJ_3_3",  "id modelName txdName meshCount drawDistance1 drawDistance2 flags timeOn timeOff")
III_structures['tobj_4'] = namedtuple("IDE_TOBJ_3_4",  "id modelName txdName meshCount drawDistance1 drawDistance2 drawDistance3 flags timeOn timeOff")

VC_structures['tobj_1'] =  namedtuple("IDE_TOBJ_VC_1",  "id modelName txdName drawDistance flags timeOn timeOff")
VC_structures['tobj_2'] =  namedtuple("IDE_TOBJ_VC_2",  "id modelName txdName meshCount drawDistance flags timeOn timeOff")
VC_structures['tobj_3'] =  namedtuple("IDE_TOBJ_VC_3",  "id modelName txdName meshCount drawDistance1 drawDistance2 flags timeOn timeOff")
VC_structures['tobj_4'] =  namedtuple("IDE_TOBJ_VC_4",  "id modelName txdName meshCount drawDistance1 drawDistance2 drawDistance3 flags timeOn timeOff")

SA_structures['tobj_1'] =  namedtuple("IDE_TOBJ_SA_1",  "id modelName txdName drawDistance flags timeOn timeOff")
SA_structures['tobj_2'] =  namedtuple("IDE_TOBJ_SA_2",  "id modelName txdName meshCount drawDistance flags timeOn timeOff")
SA_structures['tobj_3'] =  namedtuple("IDE_TOBJ_SA_3",  "id modelName txdName meshCount drawDistance1 drawDistance2 flags timeOn timeOff")
SA_structures['tobj_4'] =  namedtuple("IDE_TOBJ_SA_4",  "id modelName txdName meshCount drawDistance1 drawDistance2 drawDistance3 flags timeOn timeOff")

# ANIM
# Defines animated objects. The section functions similarly to objs but has one
# additional parameter indicating an IFP or WAD animation file to assign an
# animation to the object. 
SA_structures['anim'] = namedtuple("IDE_ANIM_SA", "id modelName textureName animName drawDist flags")

# PEDS
# Defines pedestrian objects (random NPC's)
III_structures['peds'] = namedtuple("IDE_PEDS_3",  "id modelName txdName pedType behavior animGroup vehClass")
VC_structures['peds'] =  namedtuple("IDE_PEDS_VC", "id modelName txdName pedType behavior animGroup vehClass animfile radio1 radio2")
SA_structures['peds'] =  namedtuple("IDE_PEDS_SA", "id modelName txdName pedType behavior animGroup vehClass flags animfile radio1 radio2 voiceArchive voice1 voice2")

# CARS
# Defines vehicle objects
# See: https://www.grandtheftwiki.com/CARS_(IDE_Section)
III_structures['cars_boat'] =  namedtuple("IDE_CARS_3_BOAT",  "id modelName txdName type handlingId gameName vehicleClass frequency level compRules")
III_structures['cars_train'] = namedtuple("IDE_CARS_3_TRAIN", "id modelName txdName type handlingId gameName vehicleClass frequency level compRules")
III_structures['cars_heli'] =  namedtuple("IDE_CARS_3_HELI",  "id modelName txdName type handlingId gameName vehicleClass frequency level compRules")
III_structures['cars_plane'] = namedtuple("IDE_CARS_3_PLANE", "id modelName txdName type handlingId gameName vehicleClass frequency level compRules lodModel")
III_structures['cars_car'] =   namedtuple("IDE_CARS_3_CAR",   "id modelName txdName type handlingId gameName vehicleClass frequency level compRules wheelId wheelScale")

VC_structures['cars_boat'] =   namedtuple("IDE_CARS_VC_BOAT",  "id modelName txdName type handlingId gameName anims vehicleClass frequency level compRules")
VC_structures['cars_heli'] =   namedtuple("IDE_CARS_VC_HELI",  "id modelName txdName type handlingId gameName anims vehicleClass frequency level compRules")
VC_structures['cars_plane'] =  namedtuple("IDE_CARS_VC_PLANE", "id modelName txdName type handlingId gameName anims vehicleClass frequency level compRules lodModel")
VC_structures['cars_car'] =    namedtuple("IDE_CARS_VC_CAR",   "id modelName txdName type handlingId gameName anims vehicleClass frequency level compRules wheelId wheelScale")
VC_structures['cars_bike'] =   namedtuple("IDE_CARS_VC_BIKE",  "id modelName txdName type handlingId gameName anims vehicleClass frequency level compRules steeringAngle wheelScale")

SA_structures['cars'] =        namedtuple("IDE_CARS_SA", "id modelName txdName type handlingId gameName anims vehicleClass frequency flags comprules wheelId wheelScaleFront wheelScaleRear unknownValue")

# HIER
# Defines clump objects for use in cutscenes
SA_structures['hier'] = namedtuple("IDE_HIER_SA", "id modelName txdName")

# TXDP
# Used as an extended texture archive
SA_structures['txpd'] = namedtuple("IDE_TXDP_SA", "txdName txdParentName")

# WEAP
# Used to define weapon objects
VC_structures['weap'] = namedtuple("IDE_WEAP_VC", "id modelName txdName animationName meshCount drawDistance")
SA_structures['weap'] = namedtuple("IDE_WEAP_SA", "id modelName txdName animationName meshCount drawDistance")



###################
#    IDE paths    #
###################

# Paths to IDE files for each game
# All IDEs should  be always loaded when importing maps
# ANY IDEs must be re-imported via "Import IDE" function for export

#GTA III
III_IDE = (
    'DATA\\MAPS\\generic.IDE',
    'DATA\\MAPS\\INDUSTNE\\INDUSTNE.ide',
    'DATA\\MAPS\\INDUSTNW\\INDUSTNW.ide',
    'DATA\\MAPS\\INDUSTSE\\INDUSTSE.ide',
    'DATA\\MAPS\\INDUSTSW\\INDUSTSW.ide',
    'DATA\\MAPS\\MAKING\\MAKING.ide',
    'DATA\\MAPS\\TEMPPART\\TEMPPART.ide',
    'DATA\\MAPS\\INDROADS\\INDROADS.ide',
    'DATA\\MAPS\\COMNtop\\COMNtop.ide',
    'DATA\\MAPS\\COMNbtm\\COMNbtm.ide',
    'DATA\\MAPS\\COMSE\\COMSE.ide',
    'DATA\\MAPS\\COMSW\\COMSW.ide',
    'DATA\\MAPS\\COMROAD\\COMROAD.ide',
    'DATA\\MAPS\\LANDne\\LANDne.ide',
    'DATA\\MAPS\\LANDsw\\LANDsw.ide',
    'DATA\\MAPS\\SUBROADS\\SUBROADS.ide'
)

#GTA VC
VC_IDE = (
    'DATA\\MAPS\\generic.IDE',
    'DATA\\MAPS\\littleha\\littleha.IDE',
    'DATA\\MAPS\\downtown\\downtown.IDE',
    'DATA\\MAPS\\downtows\\downtows.IDE',
    'DATA\\MAPS\\docks\\docks.IDE',
    'DATA\\MAPS\\washintn\\washintn.IDE',
    'DATA\\MAPS\\washints\\washints.IDE',
    'DATA\\MAPS\\oceandrv\\oceandrv.IDE',
    'DATA\\MAPS\\oceandn\\oceandn.IDE',
    'DATA\\MAPS\\golf\\golf.IDE',
    'DATA\\MAPS\\bridge\\bridge.IDE',
    'DATA\\MAPS\\starisl\\starisl.IDE',
    'DATA\\MAPS\\nbeachbt\\nbeachbt.IDE',
    'DATA\\MAPS\\nbeachw\\nbeachw.IDE',
    'DATA\\MAPS\\nbeach\\nbeach.IDE',
    'DATA\\MAPS\\bank\\bank.IDE',
    'DATA\\MAPS\\mall\\mall.IDE',
    'DATA\\MAPS\\yacht\\yacht.IDE',
    'DATA\\MAPS\\cisland\\cisland.IDE',
    'DATA\\MAPS\\club\\club.IDE',
    'DATA\\MAPS\\hotel\\hotel.IDE',
    'DATA\\MAPS\\lawyers\\lawyers.IDE',
    'DATA\\MAPS\\stripclb\\stripclb.IDE',
    'DATA\\MAPS\\airport\\airport.IDE',
    'DATA\\MAPS\\airportN\\airportN.IDE',
    'DATA\\MAPS\\haiti\\haiti.IDE',
    'DATA\\MAPS\\haitin\\haitin.IDE',
    'DATA\\MAPS\\concerth\\concerth.IDE',
    'DATA\\MAPS\\mansion\\mansion.IDE',
    'DATA\\MAPS\\islandsf\\islandsf.IDE',
    'DATA\\MAPS\\stadint\\stadint.IDE'
)

#GTA SA
SA_IDE = (
    'DATA\\MAPS\\generic\\vegepart.IDE',
    'DATA\\MAPS\\generic\\barriers.IDE',
    'DATA\\MAPS\\generic\\dynamic.IDE',
    'DATA\\MAPS\\generic\\dynamic2.IDE',
    'DATA\\MAPS\\generic\\multiobj.IDE',
    'DATA\\MAPS\\generic\\procobj.IDE',
    'DATA\\MAPS\\LA\\LAn2.IDE',
    'DATA\\MAPS\\LA\\LAs.IDE',
    'DATA\\MAPS\\LA\\LAs2.IDE',
    'DATA\\MAPS\\LA\\LAe.IDE',
    'DATA\\MAPS\\LA\\LAe2.IDE',
    'DATA\\MAPS\\LA\\LAw2.IDE',
    'DATA\\MAPS\\LA\\LAw.IDE',
    'DATA\\MAPS\\LA\\LAwn.IDE',
    'DATA\\MAPS\\LA\\LAhills.IDE',
    'DATA\\MAPS\\LA\\LAxref.IDE',
    'DATA\\MAPS\\SF\\SFn.IDE',
    'DATA\\MAPS\\SF\\SFs.IDE',
    'DATA\\MAPS\\SF\\SFse.IDE',
    'DATA\\MAPS\\SF\\SFe.IDE',
    'DATA\\MAPS\\SF\\SFw.IDE',
    'DATA\\MAPS\\SF\\SFxref.IDE',
    'DATA\\MAPS\\vegas\\vegasN.IDE',
    'DATA\\MAPS\\vegas\\vegasS.IDE',
    'DATA\\MAPS\\vegas\\vegasE.IDE',
    'DATA\\MAPS\\vegas\\vegasW.IDE',
    'DATA\\MAPS\\vegas\\vegaxref.IDE',
    'DATA\\MAPS\\country\\countryN.IDE',
    'DATA\\MAPS\\country\\countN2.IDE',
    'DATA\\MAPS\\country\\countryS.IDE',
    'DATA\\MAPS\\country\\countryE.IDE',
    'DATA\\MAPS\\country\\countryW.IDE',
    'DATA\\MAPS\\country\\counxref.IDE',
    'DATA\\MAPS\\interior\\int_LA.IDE',
    'DATA\\MAPS\\interior\\int_SF.IDE',
    'DATA\\MAPS\\interior\\int_veg.IDE',
    'DATA\\MAPS\\interior\\int_cont.IDE',
    'DATA\\MAPS\\leveldes\\levelmap.IDE',
    'DATA\\MAPS\\leveldes\\levelxre.IDE',
    'DATA\\MAPS\\interior\\gen_int1.IDE',
    'DATA\\MAPS\\interior\\gen_int2.IDE',
    'DATA\\MAPS\\interior\\gen_intb.IDE',
    'DATA\\MAPS\\interior\\gen_int3.IDE',
    'DATA\\MAPS\\interior\\gen_int4.IDE',
    'DATA\\MAPS\\interior\\gen_int5.IDE',
    'DATA\\MAPS\\interior\\savehous.IDE',
    'DATA\\MAPS\\interior\\stadint.IDE',
    'DATA\\MAPS\\leveldes\\seabed.IDE',
    'DATA\\MAPS\\interior\\props.IDE',
    'DATA\\MAPS\\interior\\props2.IDE',
    'DATA\\MAPS\\interior\\propext.IDE',
    'DATA\\MAPS\\veh_mods\\veh_mods.IDE',
    'DATA\\MAPS\\beach\\beach.ide'
)

# GTA LCS - this uses LCS PC Edition
LCS_IDE = (
    'DATA\\MAPS\\SUBURB.IDE',
    'DATA\\MAPS\\SUBROADS.IDE',
    'DATA\\MAPS\\COMMER.IDE',
    'DATA\\MAPS\\COMROAD.IDE',
    'DATA\\MAPS\\INDUST.IDE',
    'DATA\\MAPS\\INDROADS.IDE',
    'DATA\\MAPS\\FORTDESTROYED.IDE',
    'DATA\\MAPS\\FORTSTAUNTON.IDE'

)

#GTA VCS - this uses VCS PC Edition
VCS_IDE = (
    'DATA\\MAPS\\generic\\vegepart.IDE',
    'DATA\\MAPS\\generic\\barriers.IDE',
    'DATA\\MAPS\\generic\\dynamic.IDE',
    'DATA\\MAPS\\generic\\dynamic2.IDE',
    'DATA\\MAPS\\generic\\multiobj.IDE',
    'DATA\\MAPS\\generic\\procobj.IDE',
    'DATA\\MAPS\\leveldes\\levelxre.IDE',
    'DATA\\MAPS\\airport\\airport.IDE',
    'DATA\\MAPS\\littleha\\littleha.IDE',
    'DATA\\MAPS\\airportN\\airportN.IDE',
    'DATA\\MAPS\\docks\\docks.IDE',
    'DATA\\MAPS\\mansion\\mansion.IDE',
    'DATA\\MAPS\\starisl\\starisl.IDE',
    'DATA\\MAPS\\haiti\\haiti.IDE',
    'DATA\\MAPS\\haitiN\\haitiN.IDE',
    'DATA\\MAPS\\bridge\\bridge.IDE',
    'DATA\\MAPS\\golf\\golf.IDE',
    'DATA\\MAPS\\downtowS\\downtowS.IDE',
    'DATA\\MAPS\\downtowN\\downtowN.IDE',
    'DATA\\MAPS\\cisland\\cisland.IDE',
    'DATA\\MAPS\\nbeachw\\nbeachw.IDE',
    'DATA\\MAPS\\islandsf\\islandsf.IDE',
    'DATA\\MAPS\\oceandn\\oceandn.IDE',
    'DATA\\MAPS\\oceandrv\\oceandrv.IDE',
    'DATA\\MAPS\\nbeach\\nbeach.IDE',
    'DATA\\MAPS\\nbeachbt\\nbeachbt.IDE',
    'DATA\\MAPS\\washintN\\washintN.IDE',
    'DATA\\MAPS\\washintS\\washintS.IDE',
    'DATA\\MAPS\\mall\\mall.IDE',
    'DATA\\MAPS\\shops\\shops.IDE',
    'DATA\\MAPS\\empire\\empire.IDE',
    'DATA\\MAPS\\stadium\\stadium.IDE'

)

#GTA IV - this uses VxIV2SA(MUST be mobile version to avoid crappy Fastman92 encryption)
IV_IDE = (
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKN.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKN2.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKS.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKS2.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKS3.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXE.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXE2.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXW.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXW2.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH1.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH2.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH3.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH4.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH5.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH6.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH7.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH8.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH9.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH10.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH11.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH12.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ1.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ2.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ3.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ4e.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ4w.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ5.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJDC.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJLB.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSE.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSM.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSW.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSW2.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\INTS.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\PROPS.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\XREA.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\XRMH.IDE',
        'com.rockstargames.gtasa\\files\\DATA\\MAPS\\XRNJ.IDE'
)

###################
#    IPL paths    #
###################

# Paths to IPL files for each game

# GTA III
III_IPL = (
    ('DATA\\MAPS\\INDUSTNE\\INDUSTNE.IPL', 'industne', ''),
    ('DATA\\MAPS\\INDUSTNW\\INDUSTNW.IPL', 'industnw', ''),
    ('DATA\\MAPS\\INDUSTSE\\INDUSTSE.IPL', 'industse', ''),
    ('DATA\\MAPS\\INDUSTSW\\INDUSTSW.IPL', 'industsw', ''),
    ('DATA\\MAPS\\COMNtop\\COMNtop.IPL',   'comntop', ''),
    ('DATA\\MAPS\\COMNbtm\\COMNbtm.IPL',   'comnbtm', ''),
    ('DATA\\MAPS\\COMSE\\COMSE.IPL',       'comse', ''),
    ('DATA\\MAPS\\COMSW\\COMSW.IPL',       'comsw', ''),
    ('DATA\\MAPS\\LANDne\\LANDne.IPL',     'landne', ''),
    ('DATA\\MAPS\\LANDsw\\LANDsw.IPL',     'landsw', ''),
    ('DATA\\MAPS\\overview.IPL',           'overview', ''),
    ('DATA\\MAPS\\props.IPL',              'props', ''),
    ('DATA\\MAPS\\CULL.IPL',               'cull', '')
)

# GTA VC
VC_IPL = (
    ('DATA\\MAPS\\littleha\\littleha.IPL', 'littleha', ''),
    ('DATA\\MAPS\\downtown\\downtown.IPL', 'downtown', ''),
    ('DATA\\MAPS\\downtows\\downtows.IPL', 'downtows', ''),
    ('DATA\\MAPS\\docks\\docks.IPL',       'docks', ''),
    ('DATA\\MAPS\\washintn\\washintn.IPL', 'washintn', ''),
    ('DATA\\MAPS\\washints\\washints.IPL', 'washints', ''),
    ('DATA\\MAPS\\oceandrv\\oceandrv.IPL', 'oceandrv', ''),
    ('DATA\\MAPS\\oceandn\\oceandn.IPL',   'oceandn', ''),
    ('DATA\\MAPS\\golf\\golf.IPL',         'golf', ''),
    ('DATA\\MAPS\\bridge\\bridge.IPL',     'bridge', ''),
    ('DATA\\MAPS\\starisl\\starisl.IPL',   'starisl', ''),
    ('DATA\\MAPS\\nbeachbt\\nbeachbt.IPL', 'nbeachbt', ''),
    ('DATA\\MAPS\\nbeach\\nbeach',     'nbeach', ''),
    ('DATA\\MAPS\\nbeachw\\nbeachw.IPL',   'nbeachw', ''),
    ('DATA\\MAPS\\cisland\\cisland.IPL',   'cisland', ''),
    ('DATA\\MAPS\\airport\\airport.IPL',   'airport', ''),
    ('DATA\\MAPS\\airportN\\airportN.IPL', 'airportN', ''),
    ('DATA\\MAPS\\haiti\\haiti.IPL',       'haiti', ''),
    ('DATA\\MAPS\\haitin\\haitin.IPL',     'haitin', ''),
    ('DATA\\MAPS\\islandsf\\islandsf.IPL', 'islandsf', ''),
    ('DATA\\MAPS\\stadint\\stadint.IPL',   'stadint', ''),
    ('DATA\\MAPS\\paths.ipl',              'paths', ''),
    ('DATA\\MAPS\\cull.ipl',               'cull', ''),
    ('DATA\\occlu.ipl',                    'occlu', ''),
    ('DATA\\MAPS\\bank\\bank.IPL',         'bank', ''),
    ('DATA\\MAPS\\mall\\mall.IPL',         'mall', ''),
    ('DATA\\MAPS\\yacht\\yacht.IPL',       'yacht', ''),
    ('DATA\\MAPS\\club\\club.IPL',         'club', ''),
    ('DATA\\MAPS\\hotel\\hotel.IPL',       'hotel', ''),
    ('DATA\\MAPS\\lawyers\\lawyers.IPL',   'lawyers', ''),
    ('DATA\\MAPS\\stripclb\\stripclb.IPL', 'stripclb', ''),
    ('DATA\\MAPS\\concerth\\concerth.IPL', 'concerth', ''),
    ('DATA\\MAPS\\mansion\\mansion.IPL',   'mansion', '')
)

# GTA SA
SA_IPL = (

    ('DATA\\MAPS\\LA\\LAn2.IPL',           'LAn2', ''),
    ('DATA\\MAPS\\LA\\LAs.IPL',            'LAs', ''),
    ('DATA\\MAPS\\LA\\LAs2.IPL',           'LAs2', ''),
    ('DATA\\MAPS\\LA\\LAe.WPL',            'LAe', ''),
    ('DATA\\MAPS\\LA\\LAe2.IPL',           'LAe2', ''),
    ('DATA\\MAPS\\LA\\LAw.IPL',            'LAw', ''),
    ('DATA\\MAPS\\LA\\LAwn.IPL',           'LAwn', ''),
    ('DATA\\MAPS\\LA\\LAw2.IPL',           'LAw2', ''),
    ('DATA\\MAPS\\LA\\LAhills.IPL',        'LAhills', ''),
    ('DATA\\MAPS\\SF\\SFn.IPL',            'SFn', ''),
    ('DATA\\MAPS\\SF\\SFs.IPL',            'SFs', ''),
    ('DATA\\MAPS\\SF\\SFse.IPL',           'SFse', ''),
    ('DATA\\MAPS\\SF\\SFe.IPL',            'SFe', ''),
    ('DATA\\MAPS\\SF\\SFw.IPL',            'SFw', ''),
    ('DATA\\MAPS\\vegas\\vegasN.IPL',      'vegasN', ''),
    ('DATA\\MAPS\\vegas\\vegasS.IPL',      'vegasS', ''),
    ('DATA\\MAPS\\vegas\\vegasE.IPL',      'vegasE', ''),
    ('DATA\\MAPS\\vegas\\vegasW.IPL',      'vegasW', ''),
    ('DATA\\MAPS\\country\\countryN.IPL',  'countryN', ''),
    ('DATA\\MAPS\\country\\countN2.IPL',   'countN2', ''),
    ('DATA\\MAPS\\country\\countrys.IPL',  'countrys', ''),
    ('DATA\\MAPS\\country\\countryE.IPL',  'countryE', ''),
    ('DATA\\MAPS\\country\\countryW.IPL',  'countryW', ''),
    ('DATA\\MAPS\\interior\\int_LA.IPL',   'int_LA', ''),
    ('DATA\\MAPS\\interior\\int_SF.IPL',   'int_SF', ''),
    ('DATA\\MAPS\\interior\\int_veg.IPL',  'int_veg', ''),
    ('DATA\\MAPS\\interior\\int_cont.IPL', 'int_cont', ''),
    ('DATA\\MAPS\\interior\\gen_int1.IPL', 'gen_int1', ''),
    ('DATA\\MAPS\\interior\\gen_int2.IPL', 'gen_int2', ''),
    ('DATA\\MAPS\\interior\\gen_intb.IPL', 'gen_intb', ''),
    ('DATA\\MAPS\\interior\\gen_int3.IPL', 'gen_int3', ''),
    ('DATA\\MAPS\\interior\\gen_int4.IPL', 'gen_int4', ''),
    ('DATA\\MAPS\\interior\\gen_int5.IPL', 'gen_int5', ''),
    ('DATA\\MAPS\\interior\\stadint.IPL',  'stadint', ''),
    ('DATA\\MAPS\\interior\\savehous.IPL', 'savehous', ''),
    ('DATA\\MAPS\\leveldes\\levelmap.IPL', 'levelmap', ''),
    ('DATA\\MAPS\\leveldes\\seabed.IPL',   'seabed', ''),
    ('DATA\\MAPS\\paths.ipl',              'paths', ''),
    ('DATA\\MAPS\\paths2.ipl',             'paths2', ''),
    ('DATA\\MAPS\\paths3.ipl',             'paths3', ''),
    ('DATA\\MAPS\\paths4.ipl',             'paths4', ''),
    ('DATA\\MAPS\\paths5.ipl',             'paths5', ''),
    ('DATA\\MAPS\\cull.ipl',               'cull', ''),
    ('DATA\\MAPS\\tunnels.ipl',            'tunnels', ''),
    ('DATA\\MAPS\\occluSF.ipl',            'occluSF', ''),
    ('DATA\\MAPS\\occluveg.ipl',           'occluveg', ''),
    ('DATA\\MAPS\\occluLA.ipl',            'occluLA', ''),
    ('DATA\\MAPS\\occluint.ipl',           'occluint', ''),
    ('DATA\\MAPS\\audiozon.ipl',           'audiozon', '')
)

#GTA LCS - uses LCS PC Edition
LCS_IPL = (
    ('DATA\\MAPS\\temppart.ipl',                     'temppart', ''),
    ('DATA\\MAPS\\suburb.ipl',                       'suburb', ''),
    ('DATA\\MAPS\\subroads.ipl',                     'subroads', ''),
    ('DATA\\MAPS\\indust.ipl',                       'indust', ''),
    ('DATA\\MAPS\\indroads.ipl',                     'indroads', ''),
    ('DATA\\MAPS\\commer.ipl',                       'commer', ''),
    ('DATA\\MAPS\\comroad.ipl',                      'comroad', ''),
    ('DATA\\MAPS\\fortstaunton.ipl',                 'fort_staunton', ''),
    ('DATA\\MAPS\\fortdestroyed.ipl',                'fort_destroyed', '')
)

# GTA VCS - uses VCS PC Edition
VCS_IPL = (
    ('DATA\\MAPS\\littleha\\littleha.IPL', 'littleha', ''),
    ('DATA\\MAPS\\airport\\airport.IPL',   'airport', ''),
    ('DATA\\MAPS\\airportN\\airportN.IPL', 'airportN', ''),
    ('DATA\\MAPS\\docks\\docks.IPL',       'docks', ''),
    ('DATA\\MAPS\\mansion\\mansion.IPL',   'mansion', ''),
    ('DATA\\MAPS\\starisl\\starisl.IPL',   'starisl', ''),
    ('DATA\\MAPS\\haiti\\haiti.IPL',       'haiti', ''),
    ('DATA\\MAPS\\haitiN\\haitiN.IPL',     'haitiN', ''),
    ('DATA\\MAPS\\bridge\\bridge.IPL',     'bridge', ''),
    ('DATA\\MAPS\\golf\\golf.IPL',         'golf', ''),
    ('DATA\\MAPS\\downtowS\\downtowS.IPL', 'downtowS', ''),
    ('DATA\\MAPS\\downtowN\\downtowN.IPL', 'downtowN', ''),
    ('DATA\\MAPS\\cisland\\cisland.IPL',   'cisland', ''),
    ('DATA\\MAPS\\nbeachw\\nbeachw.IPL',   'nbeachw', ''),
    ('DATA\\MAPS\\islandsf\\islandsf.IPL', 'islandsf', ''),
    ('DATA\\MAPS\\oceandn\\oceandn.IPL',   'oceandn', ''),
    ('DATA\\MAPS\\oceandrv\\oceandrv.IPL', 'oceandrv', ''),
    ('DATA\\MAPS\\nbeach\\nbeach.IPL',     'nbeach', ''),
    ('DATA\\MAPS\\nbeachbt\\nbeachbt.IPL', 'nbeachbt', ''),
    ('DATA\\MAPS\\mall\\mall.IPL',         'mall', ''),
    ('DATA\\MAPS\\washintN\\washintN.IPL', 'washintN', ''),
    ('DATA\\MAPS\\washintS\\washintS.IPL', 'washintS', ''),
    ('DATA\\MAPS\\shops\\shops.IPL',       'shops', ''),
    ('DATA\\MAPS\\empire\\empire.IPL',     'empire', ''),
    ('DATA\\MAPS\\stadium\\stadium.IPL',   'stadium', '')
)

# GTA IV - uses VxIV2SA(SLOW)
IV_IPL = (
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKN.IPL', 'BKN', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKN2.IPL', 'BKN2', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKS.IPL', 'BKS', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKS2.IPL', 'BKS2', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BKS3.IPL', 'BKS3', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXE.IPL', 'BXE', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXE2.IPL', 'BXE2', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXW.IPL', 'BXW', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\BXW2.IPL', 'BXW2', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH1.IPL', 'MH1', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH2.IPL', 'MH2', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH3.IPL', 'MH3', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH4.IPL', 'MH4', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH5.IPL', 'MH5', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH6.IPL', 'MH6', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH7.IPL', 'MH7', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH8.IPL', 'MH8', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH9.IPL', 'MH9', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH10.IPL', 'MH10', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH11.IPL', 'MH11', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\MH12.IPL', 'MH12', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ1.IPL', 'NJ1', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ2.IPL', 'NJ2', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ3.IPL', 'NJ3', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ4e.IPL', 'NJ4e', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ4w.IPL', 'NJ4w', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJ5.IPL', 'NJ5', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJDC.IPL', 'NJDC', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\NJLB.IPL', 'NJLB', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSE.IPL', 'QSE', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSM.IPL', 'QSM', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSW.IPL', 'QSW', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\LC\\QSW2.IPL', 'QSW2', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\INTS.IPL',    'INTS', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\PROPS.IPL',   'PROPS', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\XREA.IPL',    'XREA', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\XRMH.IPL',    'XRMH', ''),
    ('com.rockstargames.gtasa\\files\\DATA\\MAPS\\XRNJ.IPL',    'XRNJ', '')
)


# Export
data = {
    game_version.III : {
        'structures': III_structures,
        'IDE_paths': III_IDE,
        'IPL_paths': III_IPL,
    },
    game_version.VC : {
        'structures': VC_structures,
        'IDE_paths': VC_IDE,
        'IPL_paths': VC_IPL,
    },
    game_version.SA : {
        'structures': SA_structures,
        'IDE_paths': SA_IDE,
        'IPL_paths': SA_IPL,
    },
    game_version.LCS : {
        'structures': VC_structures,
        'IDE_paths': LCS_IDE,
        'IPL_paths': LCS_IPL,
    },
    game_version.VCS : {
        'structures': SA_structures,
        'IDE_paths': VCS_IDE,
        'IPL_paths': VCS_IPL,
    },
    game_version.IV : {
        'structures': SA_structures,
        'IDE_paths': IV_IDE,
        'IPL_paths': IV_IPL,
    },
}
