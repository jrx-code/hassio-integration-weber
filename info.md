# Weber Spirit / June

Read a WiFi **Weber Spirit / June** grill in Home Assistant straight from the
cloud — **no companion app, no Android VM**.

- Cavity temperature + **target (setpoint)**
- Probe temperature(s)
- Connection + mode
- Zero external dependencies (Python stdlib only)

**Read-only.** The probe *target* is not exposed by the cloud (use an
`input_number`). The live stream is single-session, so it cannot run alongside the
official app. Requires the OAuth client credentials in the environment and your
account refresh token — see the [README](https://github.com/jrx-code/hassio-integration-weber#configuration).
