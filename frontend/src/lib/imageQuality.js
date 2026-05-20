function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = url;
  });
}

function computeLuma(r, g, b) {
  return (0.299 * r) + (0.587 * g) + (0.114 * b);
}

export async function assessImageQuality(file) {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await loadImage(objectUrl);
    const canvas = document.createElement("canvas");
    const width = image.naturalWidth;
    const height = image.naturalHeight;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return {
        brightness: 0,
        sharpness: 0,
        warnings: ["Unable to evaluate image quality."],
      };
    }
    ctx.drawImage(image, 0, 0, width, height);
    const { data } = ctx.getImageData(0, 0, width, height);

    let lumaSum = 0;
    let edgeSum = 0;
    const rowStride = width * 4;
    for (let y = 0; y < height - 1; y += 1) {
      for (let x = 0; x < width - 1; x += 1) {
        const i = (y * width + x) * 4;
        const right = i + 4;
        const down = i + rowStride;
        const p = computeLuma(data[i], data[i + 1], data[i + 2]);
        const px = computeLuma(data[right], data[right + 1], data[right + 2]);
        const py = computeLuma(data[down], data[down + 1], data[down + 2]);
        lumaSum += p;
        edgeSum += Math.abs(p - px) + Math.abs(p - py);
      }
    }

    const samples = Math.max(1, (width - 1) * (height - 1));
    const brightness = lumaSum / samples;
    const sharpness = edgeSum / samples;
    const warnings = [];

    if (width < 640 || height < 640) warnings.push("Resolution is low. Capture a closer and clearer photo.");
    if (brightness < 70) warnings.push("Image appears dark. Add natural light.");
    if (sharpness < 10) warnings.push("Possible blur detected. Hold steady and refocus if results look uncertain.");

    return {
      brightness: Number(brightness.toFixed(2)),
      sharpness: Number(sharpness.toFixed(2)),
      warnings,
    };
  } catch {
    return {
      brightness: 0,
      sharpness: 0,
      warnings: ["Unable to evaluate image quality."],
    };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
