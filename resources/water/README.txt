WATER.DAT IMPORT / EXPORT

IMPORT
File > Import > DemonFF > DemonFF Water (.dat)

- Supports San Andreas triangles/quads, GTA III / Vice City text rectangles,
  and classic PC binary WATERPRO.DAT. The SA processed marker is supported
  on import and written as the first line on SA export.
- Automatic format detection; UTF-8/BOM and Windows-1252 comments are accepted.
- Commas, whitespace and inline #, ; or // comments are accepted.
- Combine Sectors imports one mesh with independent faces instead of one
  object per sector. Vertex flow/waves and face flags remain independent.
- Skip Invalid Records imports valid sectors and reports skipped source lines.
  This is disabled by default so incomplete files are not accepted silently.
- Sector objects have centered origins. Imported objects are selected.
- The supplied sa_waterclear256.png remains the default texture.
  It is packed into the blend. Compatible water materials are reused.
- Use Material Preview or Rendered shading to see the texture.
- Texture Tile Size is world units per repeat (default: 32). Initial UVs are
  world-aligned across neighbouring sectors. Moving/scaling objects also
  moves/scales their existing UV mapping with the mesh.

EDIT WATER DATA
Object Properties > DemonFF Water

- Mark selected new meshes as SA Water or III / VC Water.
- Set flags, flow X/Y, big waves and small waves in the panel.
- Apply to Entire Mesh changes values on the active object's mesh.
- In Edit Mode, Apply to Selected Vertices / Faces writes flow/wave values
  only to selected vertices and flags only to selected faces.
- Panel fields are values TO APPLY. They do not override stored mesh data
  until Apply is pressed. Flags accept decimal or 0x-prefixed hexadecimal.
- Geometry edits, joining and separating meshes retain Blender custom data.
  Vertex layers: water_flow_x, water_flow_y, water_big_waves, water_small_waves.
  Face layers: water_flags, water_sector, water_line, water_level.
- All 32 flag bits are preserved. Blender's signed integer face storage may
  display high-bit flag values as negative; export writes unsigned values.
- Existing single-sector objects from the earlier importer are supported by
  reading their water_vertex_data and water_flags custom properties.

EXPORT A NEW FILE
File > Export > DemonFF > DemonFF Water (.dat)

1. Edit imported water or create new triangle/quad mesh faces.
2. Choose Selected Meshes (default), All Water in Scene, or Water in Active Collection.
   Selected Meshes also exports unmarked geometry. The collection option
   follows the active Outliner collection and includes its children.
3. Automatic uses the source format (new meshes default to SA). Mixed source
   formats require an explicit format choice. The initial name is water_new.dat.
4. Save the file. Export uses current mesh coordinates in WORLD SPACE,
   including object/parent transforms. Unrelated scene geometry is excluded
   unless explicitly selected with Selected Meshes.

Export options:
- Apply Modifiers exports evaluated geometry without changing the source.
- Snap XY to Integers rounds SA positions to the game's integer XY grid.
  It is enabled by default and changes only the exported coordinates.
- San Andreas Geometry Checks rejects XY beyond +/-3000, fractional XY,
  quads that are not axis-aligned rectangles, and triangles with no horizontal
  edge. These are targeted shape checks, not a full game-engine validation.
  Disable for experimental/custom engine data; basic validity checks remain.
- Triangulate N-gons optionally splits faces larger than four vertices.
  SA geometry checks still apply to the resulting triangles.
- III/VC export requires flat, axis-aligned rectangles. It rejects SA flow,
  wave or flag values that the five-field format cannot store. It does not
  silently drop data during format conversion.

Missing water data on NEW SA meshes defaults to flags 0, flow (0, 0),
big waves 1.0 and small waves 0.5. New III/VC meshes use zero flow/waves.
Flow values remain game-space metadata; object rotation does not rotate them.

Every export is validated before writing. A temporary file in the output
folder is atomically renamed into place after a successful write. Failed
validation leaves an existing destination file intact. Text export writes
normalized records and does not preserve source comments or original spacing.

LIMITATIONS
Binary support targets the 21,444-byte little-endian PC WATERPRO layout.
Other binary layouts or platform variants are not supported.
Water is static preview geometry; no game water/wave/physics simulation.
Merged vertices can only hold one set of per-vertex flow/wave values.
The exporter does not raise the game's water polygon/vertex limits.

VALIDATION
Tested in Blender 4.5.3 LTS with 15 integration tests, plus 23 standalone
parser/export tests. Full DemonFF register/unregister also verified.
Supplied-file tests import/export both SA files in combined and separate
mode and verify byte-identical WATERPRO export in both grid profiles,
including a blend save/reopen and a water-height edit.

Run from the extracted DemonFF folder:
python -m unittest discover -s tests -p 'test_*.py' -v
blender --background --factory-startup --python-exit-code 1 --python tests/blender_water_checks.py

BINARY WATERPRO.DAT

Use the same Water import/export menu. Automatic detects the binary file;
WATERPRO Binary explicitly selects this codec. Automatic export follows the
imported object's format and defaults to waterpro_new.dat for binary water.
The original binary data is retained inside the blend as a Text data block,
so exporting does not depend on the source DAT still being available.

Choose WATERPRO Grid when importing:
- Vice City (default): X -2448..1648, Y -2048..2048.
- GTA III: X -2048..2048, Y -2048..2048.
There is no embedded game identifier. The file cannot distinguish these
profiles. Select the game explicitly; successful parsing alone does not
prove that the selected world-coordinate offset is correct.
Export's From Source option retains the import profile.

The fine grid is 128x128 at 32 world units per tile, stored X-major.
The coarse grid is 64x64 at 64 units. Bit 7 marks a dry cell; wet cells
reference one of 48 height/rectangle slots. Import follows the actual fine
grid rather than drawing the often much larger level-table rectangles.
Adjacent wet tiles with the same height index are merged into rectangular
faces; no dry gaps are filled. Use Combine Sectors to put these in one mesh.
The supplied WATERPRO contains 11,669 wet cells represented by 208 faces.

For binary export, use flat axis-aligned rectangles whose edges lie on the
selected game's 32-unit grid. Moving in Z changes the level. XY edits must
respect the tile grid. The writer rasterizes current geometry, allocates up
to 48 height slots, and regenerates affected coarse cells and rectangle bounds.
Unchanged coarse blocks, unused table bytes, and unrelated source values are
preserved. An unchanged import/export is byte-identical for the supplied file.
Conflicting overlapping water heights, off-grid faces, unsupported SA data,
missing source blocks, and excess height slots stop export before writing.

The three supplied files are separate inputs. WATERPRO is not treated as a
binary companion to either San Andreas text file. Export one dataset at a
time using selected meshes or its own collection.

To repeat the real-file checks (provide a directory containing the three files):
blender --background --factory-startup --python-exit-code 1 --python tests/water_supplied_checks.py -- SAMPLE_DIRECTORY


SAN ANDREAS WAVE SIMULATION AND WATER EXPORT

Select SA water, open Object Properties > DemonFF Water, and choose Build /
Refresh Wave Preview. Play or scrub the timeline. Weather Wavyness controls
the weather multiplier; Playback Speed and Time Offset control preview time.
Preview Spacing is in world units. Smaller values show more detail; 2 units
matches the fine wave sampling grid. A 250,000-vertex budget rejects overly
dense previews before replacing an existing preview. Increase spacing or
preview a smaller sector when needed.

The generated Waves object is a separate tessellated mesh. The source sectors
are hidden while it is active. Remove Wave Preview restores their previous
visibility. Disabling the add-on also removes previews and restores sources.
Preview state survives saving/reopening a blend. After editing source geometry
or per-vertex wave values, refresh the preview. Object transforms and timeline
changes are sampled on each frame. Use Apply Water Values before refreshing
to transfer the object panel's settings into per-vertex water data.

The wave calculation uses the SA PC three-component routine: 5000ms large
waves, 3500ms small waves, and 3000ms half-strength small waves. It retains
absolute integer coordinates, the two eight-entry multiplier tables, and the
256-step sine lookup. The supplied gta_sa.exe was inspected at 0x6E6EF0 and
0x8D38C8/0x8D38E8 (SHA-256:
a5112e9cbbb0d06f271399697abe2a4e76aa8ea94568f51dfea19117518d7521).
Reference implementation:
https://github.com/gta-reversed/gta-reversed/blob/master/source/game_sa/WaterLevel.cpp
The executable is not included. Python arithmetic and Blender surface normals
are used; this is a geometry preview, not a bit-exact replica of the entire
water renderer. Boat wakes, game weather progression, fog, glare, and texture
flow animation are not simulated. Weather wavyness is supplied by the panel.

Export Water (.dat) resolves a selected preview back to its source sectors.
All Water and Active Collection also omit generated preview geometry.
Export retains base heights, per-vertex flow/big/small wave values, and face
flags. Apply Modifiers applies to the source only. It never freezes animated
wave heights into water.dat. The game recreates waves from the exported data;
preview spacing, preview timing, and weather settings are not DAT fields.
Existing III/VC text and WATERPRO binary import/export remain available.
