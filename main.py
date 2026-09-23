"""
ICT Digital Twin Tool
main.py
PD
2026
"""
from modules.filemanager.filemanager import checkoutputdir, loadroom, loadassets
from modules.display.display import brownian_motion 
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
from pathlib import Path
# for testing: from pprint import pprint

output_dir = Path("data/output")
pio.templates.default = "plotly_dark"

def main():
# check if the output directory exists, if not create it
    checkoutputdir(output_dir)

# select a room layout file in YAML format
    room_layout_data = loadroom()

    # just display the details for now
    room_width = room_layout_data["room"]["width"]
    room_length = room_layout_data["room"]["length"]
    room_height = room_layout_data["room"]["height"]
    power_feed_a_voltage = room_layout_data["power"]["feed_a_voltage"]
    power_feed_a_capacity = room_layout_data["power"]["feed_a_capacity"]
    power_feed_b_voltage = room_layout_data["power"]["feed_b_voltage"]
    power_feed_b_capacity = room_layout_data["power"]["feed_b_capacity"]
    print(f"Room dimensions: {room_width}m x {room_length}m x {room_height}m")
    print(f"Power feed A: {power_feed_a_voltage}V, {power_feed_a_capacity}A, B: {power_feed_b_voltage}V, {power_feed_b_capacity}A")

# load asset data
    asset_data = loadassets()

    # validate the file structure
    expected_columns = [
    "INDEX",
    "NAME",
    "ROW",
    "RACK",
    "RACK_UNIT",
    "SIZE",
    "MODELNO"
    ]
     
    print(asset_data.columns.tolist())
    
    if list(asset_data.columns) == expected_columns:
        print("Schema validation PASSED")
    else:
        print("Schema validation FAILED")

    # print rack and device summary
    rack_counts = asset_data["RACK"].value_counts().to_dict()
    print(f"Rack counts: {rack_counts}")
    print(f"Unique devices: {asset_data['NAME'].nunique()}")
    print(f"Unique racks: {asset_data['RACK'].nunique()}")

    # print("\nDevices per rack:")
    # print(asset_data['RACK'].value_counts().sort_index())

# this will display the room layout and asset data
    # but it's just a test from plotly.com

    dates = pd.date_range('2012-01-01', '2013-02-22')
    T = (dates.max()-dates.min()).days / 365
    N = dates.size
    start_price = 100
    y = brownian_motion(T, N, sigma=0.1, S0=start_price)
    z = brownian_motion(T, N, sigma=0.1, S0=start_price)

    fig = go.Figure(data=go.Scatter3d(
        x=dates, y=y, z=z,
        marker=dict(
            size=4,
            color=z,
            colorscale='Viridis',
        ),
        line=dict(
            color='darkblue',
            width=2
        )
    ))

    fig.update_layout(
        width=800,
        height=700,
        autosize=False,
        scene=dict(
            camera=dict(
                up=dict(
                    x=0,
                    y=0,
                    z=1
                ),
                eye=dict(
                    x=0,
                    y=1.0707,
                    z=1,
                )
            ),
            aspectratio = dict( x=1, y=1, z=0.7 ),
            aspectmode = 'manual'
        ),
    )

    fig.update_layout(yaxis_title=None)
    fig.update_layout(xaxis_title=None)
    fig.update_yaxes(showticklabels=False, zeroline=False, showgrid=False)
    fig.update_xaxes(showticklabels=False, zeroline=False, showgrid=False)
    fig.write_html(f"{output_dir}/testoutput.html")
    fig.write_image(f"{output_dir}/testoutput.png")
    fig.show(config={"displayModeBar": False})
    
if __name__ == "__main__":
    main()
