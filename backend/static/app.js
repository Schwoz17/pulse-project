const userIdInput = document.getElementById("userId");
const networkType = document.getElementById("networkType");
const deviceHash = document.getElementById("deviceHash");
const sequenceInput = document.getElementById("sequence");
const keystrokeInput = document.getElementById("keystrokeInput");
const transactionAmount = document.getElementById("transactionAmount");
const submitButton = document.getElementById("submitEvent");
const resultPanel = document.getElementById("resultPanel");
const resultCard = document.getElementById("resultCard");
const actionArea = document.getElementById("actionArea");
const dashboardUserId = document.getElementById("dashboardUserId");

let sessionStarted = false;
let sessionStart = 0;
let screenSequence = [];
let keystrokeIntervals = [];
let lastKeyTime = null;

function visitScreen(screen) {
  if (!sessionStarted) {
    sessionStarted = true;
    sessionStart = Date.now();
    screenSequence = [];
    keystrokeIntervals = [];
    lastKeyTime = null;
    resultPanel.hidden = true;
  }

  if (screenSequence[screenSequence.length - 1] !== screen) {
    screenSequence.push(screen);
  }
  sequenceInput.value = JSON.stringify(screenSequence);

  if (screen === "transfer") {
    keystrokeInput.disabled = false;
    keystrokeInput.placeholder = "Type an amount or note to record typing cadence";
  }
}

keystrokeInput.addEventListener("keydown", (event) => {
  if (!sessionStarted) return;
  const now = Date.now();
  if (lastKeyTime) {
    keystrokeIntervals.push(now - lastKeyTime);
  }
  lastKeyTime = now;
});

submitButton.addEventListener("click", async () => {
  if (!sessionStarted) {
    alert("Start a session by tapping one of the screen buttons first.");
    return;
  }

  const event = {
    user_id: userIdInput.value.trim(),
    keystroke_intervals: keystrokeIntervals.length > 0 ? keystrokeIntervals : [200, 210, 190],
    session_duration_sec: (Date.now() - sessionStart) / 1000,
    screen_sequence: screenSequence,
    hour_of_day: new Date().getHours() + new Date().getMinutes() / 60,
    device_hash: deviceHash.value.trim() || "device-unknown",
    network_type: networkType.value,
  };

  if (transactionAmount.value) {
    event.transaction_amount = parseFloat(transactionAmount.value);
  }

  try {
    const response = await fetch("/session/event", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(event),
    });

    if (!response.ok) {
      const error = await response.text();
      resultCard.textContent = `Error: ${error}`;
      resultPanel.hidden = false;
      return;
    }

    const payload = await response.json();
    renderResult(payload);
  } catch (err) {
    resultCard.textContent = `Request failed: ${err.message}`;
    resultPanel.hidden = false;
  }
});

function renderResult(payload) {
  resultPanel.hidden = false;
  const decision = payload.decision;
  resultCard.className = `result-card ${decision}`;
  resultCard.innerHTML = `
    <h3>Decision: ${decision.replace("_", " ").toUpperCase()}</h3>
    <p><strong>Risk score:</strong> ${payload.risk_score}</p>
    <p><strong>Reasoning:</strong> ${payload.reasoning}</p>
    <p><strong>Source:</strong> ${payload.source}</p>
    <p><strong>Cold start:</strong> ${payload.is_cold_start}</p>
  `;

  let actionHtml = "";
  if (decision === "approve") {
    actionHtml = `<div class="action-note approve"><strong>Approved.</strong> The session is allowed and the transfer can proceed.</div>`;
  } else if (decision === "soft_challenge") {
    actionHtml = `<div class="action-note soft_challenge"><strong>Soft challenge.</strong> Ask the user for a verification step before continuing.
      <div class="row"><label>OTP code</label><input id="otpCode" placeholder="Enter OTP" /></div>
      <button onclick="verifyOtp()">Submit verification</button>
    </div>`;
  } else if (decision === "block") {
    actionHtml = `<div class="action-note block"><strong>Blocked.</strong> The session is halted and the transaction is denied.</div>`;
  }
  actionArea.innerHTML = actionHtml;
}

function verifyOtp() {
  const otp = document.getElementById("otpCode").value.trim();
  if (!otp) {
    alert("Enter the OTP to complete the soft challenge.");
    return;
  }
  actionArea.innerHTML = `<div class="action-note approve"><strong>Verification passed.</strong> After soft challenge validation, this session may proceed.</div>`;
}

function resetSession() {
  sessionStarted = false;
  screenSequence = [];
  keystrokeIntervals = [];
  lastKeyTime = null;
  sequenceInput.value = "";
  resultPanel.hidden = true;
  transactionAmount.value = "";
  keystrokeInput.value = "";
  keystrokeInput.disabled = true;
}

function openDashboard() {
  const userId = dashboardUserId.value.trim();
  if (!userId) {
    alert("Enter a user ID to view the dashboard.");
    return;
  }
  window.location.href = `/dashboard/${encodeURIComponent(userId)}`;
}

resetSession();
