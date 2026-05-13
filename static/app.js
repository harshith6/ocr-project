const fileInput = document.querySelector("#fileInput");
const cameraButton = document.querySelector("#cameraButton");
const captureButton = document.querySelector("#captureButton");
const copyButton = document.querySelector("#copyButton");
const video = document.querySelector("#video");
const canvas = document.querySelector("#canvas");
const imagePreview = document.querySelector("#imagePreview");
const statusBox = document.querySelector("#status");
const resultText = document.querySelector("#resultText");

let stream = null;
let extractedText = "";

function setStatus(message, type = "") {
  statusBox.textContent = message;
  statusBox.className = `status ${type}`.trim();
}

function showPreviewFromBlob(blob) {
  imagePreview.src = URL.createObjectURL(blob);
  imagePreview.classList.remove("hidden");
}

function stopCamera() {
  if (!stream) {
    return;
  }

  stream.getTracks().forEach((track) => track.stop());
  stream = null;
  video.srcObject = null;
  video.classList.add("hidden");
  captureButton.disabled = true;
  cameraButton.textContent = "Open Camera";
}

async function sendImage(blob, fileName = "capture.png") {
  const formData = new FormData();
  formData.append("file", blob, fileName);

  setStatus("Extracting text...", "busy");
  resultText.textContent = "";
  copyButton.disabled = true;

  const response = await fetch("/api/ocr", {
    method: "POST",
    body: formData,
  });

  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || "OCR request failed.");
  }

  extractedText = payload.text || "";
  resultText.textContent = extractedText || "No readable text found.";
  copyButton.disabled = !extractedText;
  setStatus(`Done. Found ${payload.line_count || 0} text line(s).`);
}

fileInput.addEventListener("change", async () => {
  const file = fileInput.files?.[0];
  if (!file) {
    return;
  }

  try {
    stopCamera();
    showPreviewFromBlob(file);
    await sendImage(file, file.name);
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    fileInput.value = "";
  }
});

cameraButton.addEventListener("click", async () => {
  if (stream) {
    stopCamera();
    setStatus("Camera closed.");
    return;
  }

  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });
    video.srcObject = stream;
    video.classList.remove("hidden");
    imagePreview.classList.add("hidden");
    captureButton.disabled = false;
    cameraButton.textContent = "Close Camera";
    setStatus("Camera ready. Place the document in view and capture.");
  } catch (error) {
    setStatus(`Camera access failed: ${error.message}`, "error");
  }
});

captureButton.addEventListener("click", async () => {
  if (!stream || !video.videoWidth || !video.videoHeight) {
    setStatus("Camera is not ready yet.", "error");
    return;
  }

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);

  canvas.toBlob(async (blob) => {
    if (!blob) {
      setStatus("Could not capture image.", "error");
      return;
    }

    try {
      showPreviewFromBlob(blob);
      await sendImage(blob);
    } catch (error) {
      setStatus(error.message, "error");
    }
  }, "image/png");
});

copyButton.addEventListener("click", async () => {
  if (!extractedText) {
    return;
  }

  await navigator.clipboard.writeText(extractedText);
  setStatus("Text copied.");
});
