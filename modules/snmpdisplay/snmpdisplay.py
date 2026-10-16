"""SNMP v2c polling and Plotly presentation for asset system data."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import threading

import config
import pandas as pd
import panel as pn
from panel.io.callbacks import PeriodicCallback
import plotly.graph_objects as go
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
    next_cmd,
)


_SYSTEM_OIDS = (
    "1.3.6.1.2.1.1.1.0",
    "1.3.6.1.2.1.1.3.0",
    "1.3.6.1.2.1.1.5.0",
)
_SERIAL_OIDS = (
   (
       ("tor",),
       "1.3.6.1.4.1.9.9.92.1.1.1.1.2.1",
   ),
   (
       ("computenode", "virt", "db", "app", "kube", "server", "ainode"),
       "1.3.6.1.4.1.674.10892.5.4.300.10.1.8.1",
   ),
   (("sancontroller",), "1.3.6.1.4.1.674.11000.1.3.1.1.0"),
   (("sanswitch",), "1.3.6.1.4.1.1588.2.1.1.1.3.0"),
   (("coreswitch",), "1.3.6.1.4.1.6027.3.1.1.1.3.0"),
)
_TEMPERATURE_OIDS = (
   (
       ("computenode", "virt", "db", "app", "kube", "server", "ainode"),
       "1.3.6.1.4.1.674.10892.5.4.700.20.1.6.1",
   ),
   (("tor",), "1.3.6.1.4.1.9.9.91.1.1.1.1.4.1"),
   (("sancontroller",), "1.3.6.1.4.1.674.11000.1.5.1.1.0"),
   (("coreswitch",), "1.3.6.1.4.1.6027.3.1.1.1.5.0"),
   (("sanswitch",), "1.3.6.1.4.1.1588.2.1.1.1.5.0"),
)
_POWER_OIDS = (
    (
         ("computenode", "virt", "db", "app", "kube", "server", "ainode"),
         "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.1",
    ),
)
_POWER_GETNEXT_START_OID = "1.3.6.1.4.1.674.10892.5.4.600.20.1.6.0"
_SIMULATOR_ADDRESS = "127.0.0.1"
_SIMULATOR_PORT = 1161
_RESULT_COLUMNS = (
   "Host",
   "Status",
   "Temperature",
    "Power",
   "Uptime",
   "Description",
   "Serial",
)


def _device_oid_for_device(device_name: str, oid_map: tuple[tuple[tuple[str, ...], str], ...]) -> str | None:
   """Select the vendor-specific SNMP OID used by the simulator for a device family."""
   normalized_name = device_name.lower()
   for matchers, oid in oid_map:
       if any(matcher in normalized_name for matcher in matchers):
           return oid
   return None


def _serial_oid_for_device(device_name: str) -> str | None:
   """Select the vendor serial OID used by the SNMP simulator."""
   return _device_oid_for_device(device_name, _SERIAL_OIDS)


def _temperature_oid_for_device(device_name: str) -> str | None:
   """Select the vendor temperature OID used by the SNMP simulator."""
   return _device_oid_for_device(device_name, _TEMPERATURE_OIDS)


def _power_oid_for_device(device_name: str) -> str | None:
    """Select the vendor-specific power OID used by the SNMP simulator."""
    return _device_oid_for_device(device_name, _POWER_OIDS)


def _parse_temperature_celsius(value: str) -> float | None:
   """Parse an SNMP temperature reading already reported in Celsius."""
   try:
       return float(value)
   except (TypeError, ValueError):
       return None


def _parse_power(value: str) -> float | None:
   """Parse an SNMP power reading without assuming its unit."""
   try:
       return float(value)
   except (TypeError, ValueError):
       return None


def _format_uptime(seconds: object) -> str:
   """Format an uptime value in whole hours and minutes."""
   if seconds is None or pd.isna(seconds):
       return ""

   total_minutes = int(float(seconds) // 60)
   return f"{total_minutes // 60}h {total_minutes % 60}m"


async def query_device(
   engine: SnmpEngine,
   device_name: str,
   community: str,
   target: UdpTransportTarget,
) -> dict[str, object]:
   """Fetch simulator system details and device-specific serial, temperature, and power."""
   serial_oid = _serial_oid_for_device(device_name.lower())
   temperature_oid = _temperature_oid_for_device(device_name.lower())
   power_oid = _power_oid_for_device(device_name.lower())
   requested_oids = (
       *_SYSTEM_OIDS,
       *((serial_oid,) if serial_oid else ()),
       *((temperature_oid,) if temperature_oid else ()),
   )
   error, status, index, var_binds = await get_cmd(
       engine,
       CommunityData(community, mpModel=1),
       target,
       ContextData(),
       *(ObjectType(ObjectIdentity(oid)) for oid in requested_oids),
   )
   if error:
       raise RuntimeError(str(error))
   if status:
       failed_oid = (
           requested_oids[int(index) - 1]
           if 1 <= int(index) <= len(requested_oids)
           else "unknown OID"
       )
       raise RuntimeError(f"{status.prettyPrint()} at {failed_oid}")
   if len(var_binds) != len(requested_oids):
       raise RuntimeError("The SNMP agent returned an incomplete system response.")

   description, uptime_ticks, system_name = (
       value.prettyPrint() for _, value in var_binds[:3]
   )
   serial = var_binds[3][1].prettyPrint() if serial_oid else "N/A"
   temperature_value = None
   power_value = None
   if temperature_oid:
       temperature_index = 4 if serial_oid else 3
       temperature_value = _parse_temperature_celsius(
           var_binds[temperature_index][1].prettyPrint()
       )
   if power_oid:
       try:
           power_error, power_status, _, power_var_binds = await next_cmd(
               engine,
               CommunityData(community, mpModel=1),
               target,
               ContextData(),
               ObjectType(ObjectIdentity(_POWER_GETNEXT_START_OID)),
               lexicographicMode=False,
           )
           if not power_error and not power_status and len(power_var_binds) == 1:
               power_name, power_response = power_var_binds[0]
               expected_power_oid = tuple(int(part) for part in power_oid.split("."))
               if tuple(power_name.asTuple()) == expected_power_oid:
                   power_value = _parse_power(power_response.prettyPrint())
       except (OSError, RuntimeError, asyncio.TimeoutError):
           pass
   try:
       uptime_seconds = int(uptime_ticks) / 100
   except ValueError as error:
       raise RuntimeError(f"Invalid sysUpTime response: {uptime_ticks}") from error
   return {
       "Host": device_name,
       "System name": system_name,
       "Serial": serial,
       "Description": description,
       "Temperature (°C)": temperature_value,
       "Temperature": temperature_value,
    "Power": power_value,
       "Uptime (seconds)": uptime_seconds,
       "Status": "OK",
   }


async def poll_snmp_assets(asset_data: pd.DataFrame) -> list[dict[str, object]]:
   """Poll asset SNMP names against the local simulator on UDP port 1161."""
   if not isinstance(asset_data, pd.DataFrame):
       raise TypeError("asset_data must be a pandas DataFrame")

   missing_columns = {"SNMP", "SNMP_COMMUNITY"} - set(asset_data.columns)
   if missing_columns:
       raise ValueError(
           "SNMP polling requires asset columns: "
           + ", ".join(sorted(missing_columns))
       )

   engine = SnmpEngine()
   semaphore = asyncio.Semaphore(10)

   async def poll_row(row: pd.Series) -> dict[str, object]:
       host = "" if pd.isna(row["SNMP"]) else str(row["SNMP"]).strip()
       community = (
           "" if pd.isna(row["SNMP_COMMUNITY"]) else str(row["SNMP_COMMUNITY"]).strip()
       )
       if not host:
           return {"Host": "(missing)", "Status": "Missing hostname in SNMP"}
       if not community:
           return {"Host": host, "Status": "Missing room-name community"}

       async with semaphore:
           try:
               target = await UdpTransportTarget.create(
                   (_SIMULATOR_ADDRESS, _SIMULATOR_PORT),
                   timeout=2,
                   retries=0,
               )
               normalized_name = host.lower()
               return await query_device(
                   engine,
                   host,
                   f"{community}/{normalized_name}",
                   target,
               )
           except (OSError, RuntimeError, asyncio.TimeoutError) as error:
               return {"Host": host, "Status": str(error)}

   try:
       return await asyncio.gather(
           *(poll_row(row) for _, row in asset_data.iterrows())
       )
   finally:
       engine.close_dispatcher()


def build_snmp_figure(
    samples: Sequence[Mapping[str, object]] = (),
) -> go.Figure:
    """Build a temperature time series from successful SNMP poll results."""
    figure = go.Figure()
    hosts: dict[str, list[tuple[object, object]]] = {}
    sample_keys = {key for sample in samples for key in sample.keys()}
    has_temperature = any(
        key in sample_keys for key in ("Temperature", "Temperature (°C)")
    )
    has_uptime = any(key in sample_keys for key in ("Uptime", "Uptime (seconds)"))
    title = "SNMP System Temperature" if has_temperature or not has_uptime else "SNMP System Uptime"
    yaxis_title = "Temperature (°C)" if has_temperature or not has_uptime else "Uptime (seconds)"
    empty_text = (
        "Poll SNMP devices to collect system temperature"
        if has_temperature or not has_uptime
        else "Poll SNMP devices to collect system uptime"
    )

    for sample in samples:
        host = sample.get("Host")
        timestamp = sample.get("Timestamp")
        temperature = sample.get("Temperature (°C)")
        if temperature is None:
            temperature = sample.get("Temperature")
        if temperature is None and (not has_temperature or has_uptime):
            temperature = sample.get("Uptime (seconds)")
        if temperature is None:
            temperature = sample.get("Uptime")
        if (
            sample.get("Status") == "OK"
            and isinstance(host, str)
            and timestamp is not None
            and isinstance(temperature, (int, float))
        ):
            hosts.setdefault(host, []).append((timestamp, temperature))

    for host, points in hosts.items():
        figure.add_trace(
            go.Scatter(
                x=[timestamp for timestamp, _ in points],
                y=[temperature for _, temperature in points],
                mode="lines+markers",
                name=host,
            )
        )
    if not hosts:
        figure.add_annotation(
            text=empty_text,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )

    figure.update_layout(
        title=title,
        template="plotly_white",
        autosize=True,
        height=500,
        xaxis_title="Poll time",
        yaxis_title=yaxis_title,
        margin={"l": 55, "r": 30, "t": 75, "b": 50},
    )
    return figure


def build_snmp_power_figure(
    samples: Sequence[Mapping[str, object]] = (),
) -> go.Figure:
    """Build a time series of numeric SNMP system power readings."""
    figure = go.Figure()
    hosts: dict[str, list[tuple[object, float]]] = {}

    for sample in samples:
        host = sample.get("Host")
        timestamp = sample.get("Timestamp")
        power = sample.get("Power")
        if (
            sample.get("Status") == "OK"
            and isinstance(host, str)
            and timestamp is not None
            and isinstance(power, (int, float))
        ):
            hosts.setdefault(host, []).append((timestamp, float(power)))

    for host, points in hosts.items():
        figure.add_trace(
            go.Scatter(
                x=[timestamp for timestamp, _ in points],
                y=[power for _, power in points],
                mode="lines+markers",
                name=host,
            )
        )
    if not hosts:
        figure.add_annotation(
            text="Poll supported SNMP devices to collect system power",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
        )

    figure.update_layout(
        title="SNMP System Power",
        template="plotly_white",
        autosize=True,
        height=500,
        xaxis_title="Poll time",
        yaxis_title="Power (W)",
        margin={"l": 55, "r": 30, "t": 75, "b": 50},
    )
    return figure


def build_snmp_layout(
    asset_data: pd.DataFrame | None = None,
    on_results: Callable[[list[dict[str, object]]], None] | None = None,
    refresh_button: pn.widgets.Button | None = None,
) -> pn.Column:
    """Build the SNMP panel with live polling and result history."""
    pn.extension("plotly", "tabulator")
    assets = asset_data.copy() if isinstance(asset_data, pd.DataFrame) else pd.DataFrame()
    history: list[dict[str, object]] = []
    polling = {"active": False}
    status_revision = {"value": 0}
    status = pn.pane.Alert(
        f"SNMP devices are polled every {config.SNMP_REFRESH_SECONDS} seconds "
        "while this view is open.",
        alert_type="info",
        sizing_mode="stretch_width",
    )
    results = pn.widgets.Tabulator(
        pd.DataFrame(columns=_RESULT_COLUMNS),
        height=220,
        sizing_mode="stretch_width",
        show_index=True,
        widths={"Description": 150, "Serial": 100},
    )
    chart = pn.pane.Plotly(
        build_snmp_figure(),
        config={"responsive": True},
        sizing_mode="stretch_width",
        height=500,
    )
    power_chart = pn.pane.Plotly(
        build_snmp_power_figure(),
        config={"responsive": True},
        sizing_mode="stretch_width",
        height=500,
    )
    include_refresh_button = refresh_button is None
    if refresh_button is None:
        refresh_button = pn.widgets.Button(
            label="Refresh SNMP devices",
            color="primary",
            disabled=assets.empty or not {"SNMP", "SNMP_COMMUNITY"}.issubset(assets.columns),
        )

    def set_status(message: str, alert_type: str) -> None:
        status_revision["value"] += 1
        status.object = message
        status.alert_type = alert_type
        status.visible = True

    def finish_poll(
        rows: list[dict[str, object]] | None,
        error: Exception | None,
    ) -> None:
        polling["active"] = False
        if error is not None:
            if on_results is not None:
                on_results([{"Status": str(error)} for _ in range(len(assets))])
            set_status(f"SNMP polling failed: {error}", "danger")
            return
        if rows is None:
            raise RuntimeError("SNMP polling completed without results or an error.")

        polled_at = datetime.now(timezone.utc)
        for row in rows:
            row["Timestamp"] = polled_at
        history.extend(rows)
        results_df = pd.DataFrame(rows).copy()
        if "Temperature (°C)" in results_df.columns:
            celsius_values = results_df["Temperature (°C)"]
            if "Temperature" in results_df.columns:
                celsius_values = celsius_values.combine_first(
                    results_df["Temperature"]
                )
            results_df["Temperature"] = celsius_values
        if "Uptime (seconds)" in results_df.columns:
            results_df["Uptime"] = results_df["Uptime (seconds)"].map(
                _format_uptime
            )
        results_df = results_df.reindex(columns=_RESULT_COLUMNS)
        for column in ("Temperature", "Power"):
            results_df[column] = results_df[column].astype(object).where(
                results_df[column].notna(),
                "N/A",
            )
        results.value = results_df
        chart.object = build_snmp_figure(history)
        power_chart.object = build_snmp_power_figure(history)
        if on_results is not None:
            on_results(rows)
        failures = sum(row.get("Status") != "OK" for row in rows)
        message = (
            f"Polled {len(rows)} device(s); {failures} device(s) reported an error."
            if failures
            else f"Successfully polled {len(rows)} device(s)."
        )
        alert_type = "warning" if failures else "success"
        set_status(message, alert_type)
        if not failures:
            revision = status_revision["value"]
            document = pn.state.curdoc
            if document is not None:
                def clear_status() -> None:
                    if status_revision["value"] == revision:
                        status.visible = False

                document.add_timeout_callback(clear_status, 5000)

    def on_poll(_event: object) -> None:
        if polling["active"] or assets.empty or not {
            "SNMP",
            "SNMP_COMMUNITY",
        }.issubset(assets.columns):
            return
        polling["active"] = True
        set_status("Polling SNMP devices...", "info")
        document = pn.state.curdoc

        def worker() -> None:
            try:
                rows = asyncio.run(poll_snmp_assets(assets))
            except Exception as error:
                update = lambda error=error: finish_poll(None, error)
            else:
                update = lambda: finish_poll(rows, None)
            if document is None:
                update()
            else:
                document.add_next_tick_callback(update)

        threading.Thread(target=worker, daemon=True).start()

    refresh_button.on_click(on_poll)
    panel_objects = [pn.pane.Markdown("## SNMP system data"), status]
    if include_refresh_button:
        panel_objects.append(refresh_button)
    panel_objects.extend((results, chart, power_chart))
    snmp_panel = pn.Column(
        *panel_objects,
        sizing_mode="stretch_both",
        min_height=800,
        visible=False,
    )
    periodic_callback: PeriodicCallback | None = None

    def update_polling(event: object) -> None:
        nonlocal periodic_callback
        if event.new:
            if periodic_callback is None:
                periodic_callback = pn.state.add_periodic_callback(
                    on_poll,
                    period=config.SNMP_REFRESH_SECONDS * 1000,
                    start=False,
                )
            periodic_callback.start()
            on_poll(None)
        elif periodic_callback is not None:
            periodic_callback.stop()

    snmp_panel.param.watch(update_polling, "visible")
    return snmp_panel
