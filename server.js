require("dotenv").config();
const express = require("express");
const bodyParser = require("body-parser");
const { addChannel, removeChannel, getChannels } = require("./channels");

const app = express();
app.use(bodyParser.json());

app.get("/channels", (req, res) => {
  res.json(getChannels());
});

app.post("/addChannel", (req, res) => {
  const { name, message } = req.body;
  addChannel(name, message);
  res.send("Канал добавлен");
});

app.post("/removeChannel", (req, res) => {
  const { name } = req.body;
  removeChannel(name);
  res.send("Канал удален");
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
