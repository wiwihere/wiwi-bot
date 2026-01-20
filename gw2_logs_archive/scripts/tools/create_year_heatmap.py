# %%
import pandas as pd
from _setup_django import init_django
from django.db.models import Q
from plotly import graph_objects as go

init_django(__file__)

from django.conf import settings
from gw2_logs.models import DpsLog, Encounter

window = 10

# Get encounters
encounters = list(
    Encounter.objects.filter(instance__instance_group__name__in=["raid", "strike"]).exclude(
        instance__name="IBS Strikes"
    )
)

all_data = []

for encounter in encounters:
    logs = (
        DpsLog.objects.filter(
            success=True,
            encounter=encounter.id,
            # start_time__year=2025,
        )
        .filter(Q(encounter__lb=True) | Q(encounter__lb_cm=True))
        .order_by("start_time")
        .values_list("start_time", "duration")
    )

    times = [t for t, d in logs]
    durations = [d.total_seconds() for t, d in logs]
    if not times:
        continue

    df = pd.DataFrame({"time": times, "duration": durations})

    # Normalize time to middle of the week (Wednesday at noon)
    # Assuming week starts on Monday
    df["time"] = df["time"].apply(lambda t: t - pd.Timedelta(days=t.weekday()) + pd.Timedelta(days=2, hours=12))

    df["pct"] = df["duration"].rank(pct=True)  # 0=fastest, 1=slowest
    df["encounter_name"] = encounter.name
    all_data.append(df)

df_all = pd.concat(all_data, ignore_index=True)

# Map encounters to y positions (compact)
encounter_names = df_all["encounter_name"].unique()
y_map = {name: i for i, name in enumerate(encounter_names)}
df_all["y"] = df_all["encounter_name"].map(y_map)

# Colors (same as before)
colors = df_all["pct"].apply(lambda p: f"rgb({int(p * 255)}, {int((1 - p) * 255)}, 0)")

# Scatter plot with squares
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=df_all["time"],
        y=df_all["y"],
        mode="markers",
        marker=dict(color=colors, size=15, symbol="square"),
        text=df_all["duration"],
        hovertemplate="Duration: %{text:.2f}s<br>Time: %{x}<extra></extra>",
    )
)

# Set x-axis to span full time range (weeks)
min_time = df_all["time"].min() - pd.Timedelta(days=3)  # optional padding
max_time = df_all["time"].max() + pd.Timedelta(days=3)

fig.update_layout(
    template="plotly_dark",
    yaxis=dict(
        tickvals=list(y_map.values()),
        ticktext=list(y_map.keys()),
        title="Encounter",
        autorange="reversed",
        tickfont=dict(size=10, color="white"),
    ),
    xaxis=dict(title="Time (Week-normalized)", range=[min_time, max_time], showgrid=True, gridcolor="gray"),
    title="Encounter Durations Barcode (Squares, Week-normalized)",
    height=25 * len(encounter_names) + 100,
    margin=dict(l=150, r=50, t=50, b=50),
)

output_file = settings.PROJECT_DIR.joinpath("data", "clearspeed_overview", "barcode_plot_squares_dark_week.html")
fig.write_html(output_file, include_plotlyjs="cdn")
print(f"Saved {output_file}")
