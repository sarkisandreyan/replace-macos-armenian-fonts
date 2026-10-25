import os
import re
import sys
import argparse
import subprocess
import tempfile
import platform
from fontTools import ttLib
from fontTools.ttLib.tables.TupleVariation import TupleVariation
from fontTools.ttLib import TTCollection
from fontTools.fontBuilder import FontBuilder
from fontTools.varLib import instancer

macos_version = platform.mac_ver()[0]
macos_major_version = re.match("^\\d+(?=\\.)", macos_version).group()
macos_major_version = int(macos_major_version)

parser = argparse.ArgumentParser(
    description="""
        Replace the unsightly default Armenian fonts in macOS.

        To patch the system fonts, you must first turn off System Integrity
        Protection (SIP) and Signed System Volume (SSV) from Recovery
        mode.
    """
)
parser.add_argument(
    "source_font",
    help="""
        The replacement font to use when overwriting the system fonts.
        
        The only requirement for this font is that it should have a *wght*
        (weight) axis (1-1000), and optionally an *opsz* (optical size) axis
        (17-28). Other parameters, such as units-per-em and metrics, do not
        seem to have any impact on the result and can thus have any values.

        If the font does not have an *opsz* axis, you should run this tool
        with the option '--create-dummy-opsz-axis' to create a dummy *opsz*
        axis because it is required.
""",
    type=str,
)
parser.add_argument(
    "--generate-replacements-only",
    help="""
        Generate the replacement fonts (SFArmenian.ttf & NotoSansArmenian.ttc)
        only without touching the system fonts.

        Use this option if you are planning to use the replacement fonts in a
        more non-invasive way (e.g. placing them inside `/Library/Fonts`,
        though this approach patches the fonts hardly anywhere).
    """,
    action="store_true",
)
parser.add_argument(
    "--create-dummy-opsz-axis",
    help="""
        Create a dummy *opsz* (optical size) axis in the generated replacement
        SFArmenian.ttf font for compatibility.

        Changes to the value of the dummy axis will not have any visual effect.
    """,
    action="store_true",
)

args = vars(parser.parse_args())

# Unless the --generate-replacements-only flag was set,
# check if SIP & SSV are disabled before proceeding.
if not args["generate_replacements_only"]:
    sip_check = subprocess.run(["csrutil", "status"], capture_output=True)
    svv_check = subprocess.run(
        ["csrutil", "authenticated-root", "status"], capture_output=True
    )

    sip_result = sip_check.stdout.decode("utf-8", errors="ignore")
    svv_result = svv_check.stdout.decode("utf-8", errors="ignore")

    if "enabled" in sip_result:
        print(
            "In order to be able to override system fonts, you must first disable System "
            + "Integrity Protection (SIP) and Signed System Volume (SSV). Do this at "
            + "your own risk, then come back and run this tool again."
        )
        sys.exit(1)

    if "enabled" in svv_result:
        print(
            "You have disabled System Intergrity Protection (SIP), but seem to have forgotten "
            + "to disable Signed System Volume (SVV). Do this at your own risk, then come back "
            + "and run this tool again"
        )
        sys.exit(1)

    if os.geteuid() != 0:
        print(
            "You need root privileges to be able to patch the system fonts. Run this tool with `sudo`."
        )
        sys.exit(1)

font = ttLib.TTFont(args["source_font"])


def validateFont():
    if not "fvar" in font or not "gvar" in font:
        print(
            "The provided font does not appear to be a variable font.\n"
            + "Make sure you provide a variable font with a weight axis (1-1000)."
        )
        sys.exit(1)

    fvar = font["fvar"]

    hasWght = False
    hasOpsz = False

    for axis in fvar.axes:
        if axis.axisTag == "wght":
            if axis.minValue > 1:
                print(
                    "The provided font has a weight axis (wght), but its minimum value is higher than 1."
                )
                sys.exit(1)
            if axis.maxValue < 1000:
                print(
                    "The provided font has a weight axis (wght), but its maximum value is lower than 1000."
                )
                sys.exit(1)
            hasWght = True
        if axis.axisTag == "opsz":
            if axis.minValue > 17:
                print(
                    "The provided font has an optical size axis (opsz), but its minimum value is higher than 17."
                )
                sys.exit(1)
            if axis.maxValue < 28:
                print(
                    "The provided font has an optical size axis (opsz), but its maximum value is lower than 28."
                )
                sys.exit(1)
            hasOpsz = True

    if not hasWght:
        print("The provided font does not have a weight axis (wght).")
        sys.exit(1)

    if not hasOpsz and not args["create_dummy_opsz_axis"]:
        print(
            "The provided font does not have an optical size axis (opsz). "
            + "If you want to have a dummy axis created for the optical size, "
            + "run this tool with the option --create-dummy-opsz-axis."
        )
        sys.exit(1)


def getSFVariableTFF(addOpszAxis=False):
    # Initialize font builder
    builder = FontBuilder(font=font)

    # Store gvar so as not to decompile it every time it is retrieved
    gvar = builder.font["gvar"]

    # If necessary, prepare the existing glyph variations for the
    # addition of the new axis 'opsz'.
    if addOpszAxis:
        for glyph_name, variations in gvar.variations.items():
            for variation in variations:
                variation.axes["opsz"] = (0.0, 0.0, 0.0)

    # Overwrite (or write if non-existent) the two axes
    axes = [("wght", 1, 400, 1000, "Weight"), ("opsz", 17, 28, 28, "Optical Size")]

    # Define the static instances, folling the naming of SF Armenian
    instances = [
        {
            "location": {"wght": 30.925, "opsz": 28.0},
            "stylename": "Ultralight",
            "postscriptfontname": ".SFArmenian-Ultralight",
        },
        {
            "location": {"wght": 110.725, "opsz": 28.0},
            "stylename": "Thin",
            "postscriptfontname": ".SFArmenian-Thin",
        },
        {
            "location": {"wght": 274.315, "opsz": 28.0},
            "stylename": "Light",
            "postscriptfontname": ".SFArmenian-Light",
        },
        {
            "location": {"wght": 400, "opsz": 28.0},
            "stylename": "Regular",
            "postscriptfontname": ".SFArmenian-Regular",
        },
        {
            "location": {"wght": 510.0, "opsz": 28.0},
            "stylename": "Medium",
            "postscriptfontname": ".SFArmenian-Medium",
        },
        {
            "location": {"wght": 590.0, "opsz": 28.0},
            "stylename": "Semibold",
            "postscriptfontname": ".SFArmenian-Semibold",
        },
        {
            "location": {"wght": 700.0, "opsz": 28.0},
            "stylename": "Bold",
            "postscriptfontname": ".SFArmenian-Bold",
        },
        {
            "location": {"wght": 860.0, "opsz": 28.0},
            "stylename": "Heavy",
            "postscriptfontname": ".SFArmenian-Heavy",
        },
        {
            "location": {"wght": 1000.0, "opsz": 28.0},
            "stylename": "Black",
            "postscriptfontname": ".SFArmenian-Black",
        },
    ]

    # Update the fvar table
    builder.setupFvar(axes, instances)

    # If 'opsz' axis has only been added, add three new sets of
    # glyph variations with opsz=17 (opsz=17, wght=400; opsz=17,
    # wght=1; opsz=18, wght=1000).
    if addOpszAxis:
        gvar = builder.font["gvar"]
        glyf = builder.font["glyf"]

        for glyph_name in font.getGlyphOrder():
            glyph = glyf[glyph_name]

            num_points = gvar.getNumPoints_(glyph)

            zero_deltas = [(0, 0)] * num_points

            wght_400_opsz_17 = TupleVariation(
                axes={"wght": (0.0, 0.0, 0.0), "opsz": (-1.0, -1.0, 0.0)},
                coordinates=zero_deltas,
            )

            wght_1_opsz_17 = TupleVariation(
                axes={"wght": (-1.0, -1.0, 0.0), "opsz": (-1.0, -1.0, 0.0)},
                coordinates=zero_deltas,
            )

            wght_1000_opsz_17 = TupleVariation(
                axes={"wght": (0.0, 1.0, 1.0), "opsz": (-1.0, -1.0, 0.0)},
                coordinates=zero_deltas,
            )

            gvar.variations[glyph_name].extend(
                [
                    wght_400_opsz_17,
                    wght_1_opsz_17,
                    wght_1000_opsz_17,
                ]
            )

    return builder.font


def getNotoTTC():
    # 'Thin' instance
    thin = instancer.instantiateVariableFont(font, {"wght": 1}, static=True)

    thin["OS/2"].usWeightClass = 100

    thinName = thin["name"]
    thinName.setName("Noto Sans Armenian Thin", 1, 1, 0, 0x0)
    thinName.setName("Regular", 2, 1, 0, 0x0)
    thinName.setName("Noto Sans Armenian Thin; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0)
    thinName.setName("Noto Sans Armenian Thin", 4, 1, 0, 0x0)
    thinName.setName("NotoSansArmenian-Thin", 6, 1, 0, 0x0)
    thinName.setName("Noto Sans Armenian", 16, 1, 0, 0x0)
    thinName.setName("Thin", 17, 1, 0, 0x0)
    thinName.setName("Noto Sans Armenian Thin", 1, 3, 1, 0x409)
    thinName.setName("Regular", 2, 3, 1, 0x409)
    thinName.setName("Noto Sans Armenian Thin; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409)
    thinName.setName("Noto Sans Armenian Thin", 4, 3, 1, 0x409)
    thinName.setName("NotoSansArmenian-Thin", 6, 3, 1, 0x409)
    thinName.setName("Noto Sans Armenian", 16, 3, 1, 0x409)
    thinName.setName("Thin", 17, 3, 1, 0x409)

    # 'ExtraLight' instance
    extralight = instancer.instantiateVariableFont(font, {"wght": 133}, static=True)

    extralight["OS/2"].usWeightClass = 200

    extralightName = extralight["name"]
    extralightName.setName("Noto Sans Armenian ExtLt", 1, 1, 0, 0x0)
    extralightName.setName("Regular", 2, 1, 0, 0x0)
    extralightName.setName(
        "Noto Sans Armenian ExtraLight; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0
    )
    extralightName.setName("Noto Sans Armenian ExtraLight", 4, 1, 0, 0x0)
    extralightName.setName("NotoSansArmenian-ExtraLight", 6, 1, 0, 0x0)
    extralightName.setName("Noto Sans Armenian", 16, 1, 0, 0x0)
    extralightName.setName("ExtraLight", 17, 1, 0, 0x0)
    extralightName.setName("Noto Sans Armenian ExtLt", 1, 3, 1, 0x409)
    extralightName.setName("Regular", 2, 3, 1, 0x409)
    extralightName.setName(
        "Noto Sans Armenian ExtraLight; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409
    )
    extralightName.setName("Noto Sans Armenian ExtraLight", 4, 3, 1, 0x409)
    extralightName.setName("NotoSansArmenian-ExtraLight", 6, 3, 1, 0x409)
    extralightName.setName("Noto Sans Armenian", 16, 3, 1, 0x409)
    extralightName.setName("ExtraLight", 17, 3, 1, 0x409)

    # 'Light' instance
    light = instancer.instantiateVariableFont(font, {"wght": 266}, static=True)

    light["OS/2"].usWeightClass = 300

    lightName = light["name"]
    lightName.setName("Noto Sans Armenian Light", 1, 1, 0, 0x0)
    lightName.setName("Regular", 2, 1, 0, 0x0)
    lightName.setName("Noto Sans Armenian Light; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0)
    lightName.setName("Noto Sans Armenian Light", 4, 1, 0, 0x0)
    lightName.setName("NotoSansArmenian-Light", 6, 1, 0, 0x0)
    lightName.setName("Noto Sans Armenian", 16, 1, 0, 0x0)
    lightName.setName("Light", 17, 1, 0, 0x0)
    lightName.setName("Noto Sans Armenian Light", 1, 3, 1, 0x409)
    lightName.setName("Regular", 2, 3, 1, 0x409)
    lightName.setName("Noto Sans Armenian Light; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409)
    lightName.setName("Noto Sans Armenian Light", 4, 3, 1, 0x409)
    lightName.setName("NotoSansArmenian-Light", 6, 3, 1, 0x409)
    lightName.setName("Noto Sans Armenian", 16, 3, 1, 0x409)
    lightName.setName("Light", 17, 3, 1, 0x409)

    # 'Regular' instance
    regular = instancer.instantiateVariableFont(font, {"wght": 400}, static=True)

    regular["OS/2"].usWeightClass = 400

    regularName = regular["name"]
    regularName.setName("Noto Sans Armenian", 1, 1, 0, 0x0)
    regularName.setName("Regular", 2, 1, 0, 0x0)
    regularName.setName(
        "Noto Sans Armenian Regular; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0
    )
    regularName.setName("Noto Sans Armenian Regular", 4, 1, 0, 0x0)
    regularName.setName("NotoSansArmenian-Regular", 6, 1, 0, 0x0)
    regularName.setName("Noto Sans Armenian", 1, 3, 1, 0x409)
    regularName.setName("Regular", 2, 3, 1, 0x409)
    regularName.setName(
        "Noto Sans Armenian Regular; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409
    )
    regularName.setName("Noto Sans Armenian Regular", 4, 3, 1, 0x409)
    regularName.setName("NotoSansArmenian-Regular", 6, 3, 1, 0x409)

    # 'Medium' instance
    medium = instancer.instantiateVariableFont(font, {"wght": 520}, static=True)

    medium["OS/2"].usWeightClass = 500

    mediumName = medium["name"]
    mediumName.setName("Noto Sans Armenian Med", 1, 1, 0, 0x0)
    mediumName.setName("Regular", 2, 1, 0, 0x0)
    mediumName.setName("Noto Sans Armenian Medium; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0)
    mediumName.setName("Noto Sans Armenian Medium", 4, 1, 0, 0x0)
    mediumName.setName("NotoSansArmenian-Medium", 6, 1, 0, 0x0)
    mediumName.setName("Noto Sans Armenian", 16, 1, 0, 0x0)
    mediumName.setName("Medium", 17, 1, 0, 0x0)
    mediumName.setName("Noto Sans Armenian Med", 1, 3, 1, 0x409)
    mediumName.setName("Regular", 2, 3, 1, 0x409)
    mediumName.setName(
        "Noto Sans Armenian Medium; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409
    )
    mediumName.setName("Noto Sans Armenian Medium", 4, 3, 1, 0x409)
    mediumName.setName("NotoSansArmenian-Medium", 6, 3, 1, 0x409)
    mediumName.setName("Noto Sans Armenian", 16, 3, 1, 0x409)
    mediumName.setName("Medium", 17, 3, 1, 0x409)

    # 'SemiBold' instance
    semibold = instancer.instantiateVariableFont(font, {"wght": 640}, static=True)

    semibold["OS/2"].usWeightClass = 600

    semiboldName = semibold["name"]
    semiboldName.setName("Noto Sans Armenian SemBd", 1, 1, 0, 0x0)
    semiboldName.setName("Regular", 2, 1, 0, 0x0)
    semiboldName.setName(
        "Noto Sans Armenian SemiBold; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0
    )
    semiboldName.setName("Noto Sans Armenian SemiBold", 4, 1, 0, 0x0)
    semiboldName.setName("NotoSansArmenian-SemiBold", 6, 1, 0, 0x0)
    semiboldName.setName("Noto Sans Armenian", 16, 1, 0, 0x0)
    semiboldName.setName("SemiBold", 17, 1, 0, 0x0)
    semiboldName.setName("Noto Sans Armenian SemBd", 1, 3, 1, 0x409)
    semiboldName.setName("Regular", 2, 3, 1, 0x409)
    semiboldName.setName(
        "Noto Sans Armenian SemiBold; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409
    )
    semiboldName.setName("Noto Sans Armenian SemiBold", 4, 3, 1, 0x409)
    semiboldName.setName("NotoSansArmenian-SemiBold", 6, 3, 1, 0x409)
    semiboldName.setName("Noto Sans Armenian", 16, 3, 1, 0x409)
    semiboldName.setName("SemiBold", 17, 3, 1, 0x409)

    # 'Bold' instance
    bold = instancer.instantiateVariableFont(font, {"wght": 760}, static=True)

    bold["OS/2"].usWeightClass = 700

    boldName = bold["name"]
    boldName.setName("Noto Sans Armenian", 1, 1, 0, 0x0)
    boldName.setName("Bold", 2, 1, 0, 0x0)
    boldName.setName("Noto Sans Armenian Bold; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0)
    boldName.setName("Noto Sans Armenian Bold", 4, 1, 0, 0x0)
    boldName.setName("NotoSansArmenian-Bold", 6, 1, 0, 0x0)
    boldName.setName("Noto Sans Armenian", 1, 3, 1, 0x409)
    boldName.setName("Bold", 2, 3, 1, 0x409)
    boldName.setName("Noto Sans Armenian Bold; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409)
    boldName.setName("Noto Sans Armenian Bold", 4, 3, 1, 0x409)
    boldName.setName("NotoSansArmenian-Bold", 6, 3, 1, 0x409)

    # 'ExtraBold' instance
    extrabold = instancer.instantiateVariableFont(font, {"wght": 880}, static=True)

    extrabold["OS/2"].usWeightClass = 800

    extraboldName = extrabold["name"]
    extraboldName.setName("Noto Sans Armenian ExtBd", 1, 1, 0, 0x0)
    extraboldName.setName("Regular", 2, 1, 0, 0x0)
    extraboldName.setName(
        "Noto Sans Armenian ExtraBold; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0
    )
    extraboldName.setName("Noto Sans Armenian ExtraBold", 4, 1, 0, 0x0)
    extraboldName.setName("NotoSansArmenian-ExtraBold", 6, 1, 0, 0x0)
    extraboldName.setName("Noto Sans Armenian", 16, 1, 0, 0x0)
    extraboldName.setName("ExtraBold", 17, 1, 0, 0x0)
    extraboldName.setName("Noto Sans Armenian ExtBd", 1, 3, 1, 0x409)
    extraboldName.setName("Regular", 2, 3, 1, 0x409)
    extraboldName.setName(
        "Noto Sans Armenian ExtraBold; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409
    )
    extraboldName.setName("Noto Sans Armenian ExtraBold", 4, 3, 1, 0x409)
    extraboldName.setName("NotoSansArmenian-ExtraBold", 6, 3, 1, 0x409)
    extraboldName.setName("Noto Sans Armenian", 16, 3, 1, 0x409)
    extraboldName.setName("ExtraBold", 17, 3, 1, 0x409)

    # 'Black' instance
    black = instancer.instantiateVariableFont(font, {"wght": 1000}, static=True)

    black["OS/2"].usWeightClass = 900

    blackName = black["name"]
    blackName.setName("Noto Sans Armenian Blk", 1, 1, 0, 0x0)
    blackName.setName("Regular", 2, 1, 0, 0x0)
    blackName.setName("Noto Sans Armenian Black; 15.0d1e2; 2019-03-15", 3, 1, 0, 0x0)
    blackName.setName("Noto Sans Armenian Black", 4, 1, 0, 0x0)
    blackName.setName("NotoSansArmenian-Black", 6, 1, 0, 0x0)
    blackName.setName("Noto Sans Armenian", 16, 1, 0, 0x0)
    blackName.setName("Black", 17, 1, 0, 0x0)
    blackName.setName("Noto Sans Armenian Blk", 1, 3, 1, 0x409)
    blackName.setName("Regular", 2, 3, 1, 0x409)
    blackName.setName("Noto Sans Armenian Black; 15.0d1e2; 2019-03-15", 3, 3, 1, 0x409)
    blackName.setName("Noto Sans Armenian Black", 4, 3, 1, 0x409)
    blackName.setName("NotoSansArmenian-Black", 6, 3, 1, 0x409)
    blackName.setName("Noto Sans Armenian", 16, 3, 1, 0x409)
    blackName.setName("Black", 17, 3, 1, 0x409)

    collection = TTCollection()
    collection.fonts = [
        thin,
        extralight,
        light,
        regular,
        medium,
        semibold,
        bold,
        extrabold,
        black,
    ]

    return collection


validateFont()

sfTtf = getSFVariableTFF(args["create_dummy_opsz_axis"])
notoTtc = getNotoTTC()

temp = tempfile.TemporaryDirectory()

sffile = os.path.join(temp.name, "SFArmenian.ttf")
notofile = os.path.join(temp.name, "NotoSansArmenian.ttc")

sfTtf.save(sffile)
notoTtc.save(notofile)

if args["generate_replacements_only"]:
    os.rename(sffile, "SFArmenian.ttf")
    os.rename(notofile, "NotoSansArmenian.ttc")
    print(
        f"Created the replacement fonts SFArmenian.ttf and NotoSansArmenian.ttc at {os.getcwd()}."
    )
    sys.exit()

macos_version_warning = ""

if macos_major_version < 12:
    macos_version_warning = """
The earliest macOS version this tool was tested on was Monterey 12.
Results may be unexpected on untested macOS versions.
"""
elif macos_major_version > 27:
    macos_version_warning = """
The latest macOS version this tool was tested on was Golden Gate 27.
Results may be unexpected on untested macOS versions.
"""

print(
    """!!! WARNING !!!
{macos_version_warning}
You are about to change the active boot volume of your machine. By proceeding,
you confirm that you are aware of and accept the following risks:

- The process going wrong and breaking your machine
- The patched fonts behaving in unexpected ways, including but not limited
  to not rendering text at all
- macOS behaving in unexpected ways after the process
- Any other unexpected adverse effects not listed here

By proceeding, you accept all risks associated with use of the tool and agree
that the developer, contributors, and their respective officers and agents
shall have no liability for any claims, losses, damages, or expenses (including
legal fees). You agree to indemnify and hold harmless the developer from any
third-party claims resulting from your use or modification of the tool.
""".format(macos_version_warning=macos_version_warning)
)

confirmation = input(
    "Type the word CONFIRM and press Enter to proceed (or press Enter now to exit):\n"
)

if confirmation != "CONFIRM":
    print(
        """
Aborting. If you have changed your mind and don't want to change the system
fonts anymore, remember to re-enable System Intergrity Protection (SIP) and
Signed System Volume (SSV).
"""
    )
    sys.exit(1)

efitemp = tempfile.TemporaryDirectory(delete=False)
sysfontsdir = os.path.join(efitemp.name, "System", "Library", "Fonts")

os.chmod(efitemp.name, 0o755)

disk_check = subprocess.run(["mount"], check=True, capture_output=True)
disk_result = disk_check.stdout.decode("utf-8", errors="ignore")
disk_regex = re.search(r"^(/dev/disk\ds\d).* on / ", disk_result)

if not disk_regex or not disk_regex.group(1):
    print("Could not retrieve the active boot volume. Aborting.")
    sys.exit(1)

parsed_disk = disk_regex.group(1)

try:
    # Mount the disk to a temporary location
    subprocess.run(
        f"/sbin/mount -o nobrowse -t apfs {parsed_disk} {efitemp.name}",
        shell=True,
        check=True,
    )
except subprocess.CalledProcessError:
    print("Failed to mount the disk. Aborting.")
    efitemp.cleanup()
    sys.exit(1)

# Patch the system fonts SF Armenian and Noto Sans Armenian
subprocess.run(f"cp {sffile} {notofile} {sysfontsdir}", shell=True)
# Bless the new mount point as the boot volume
subprocess.run(f"bless --mount {efitemp.name} --bootefi --create-snapshot", shell=True)
# Unmount the volume once blessed
subprocess.run(f"/sbin/umount {efitemp.name}", shell=True)

print(
    """
Successfully changed the active boot volume with the patched fonts.
Restart your machine for the changes to take effect.

If you like the end result, you can buy me a coffee at buymeacoffee.com/krmapet ;)
"""
)
