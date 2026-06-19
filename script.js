function generate() {
  const input = document.getElementById("inputText").value;

  if (!input) {
    alert("စာထည့်ပါ");
    return;
  }

  const output = `1
00:00:01 --> 00:00:03
${input} (Myanmar Subtitle)`;

  document.getElementById("output").innerText = output;
}
