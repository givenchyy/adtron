const sqlite3 = require("sqlite3").verbose();
const db = new sqlite3.Database("./bot.db");

// Создание таблиц при запуске
db.serialize(() => {
  db.run(`
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT UNIQUE
        )
    `);

  db.run(`
        CREATE TABLE IF NOT EXISTS user_channels (
            user_id INTEGER,
            channel_name TEXT,
            FOREIGN KEY(channel_name) REFERENCES channels(channel_name)
        )
    `);

  db.run(`
        CREATE TABLE IF NOT EXISTS post_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_name TEXT,
            post_template TEXT,
            status TEXT,
            FOREIGN KEY(channel_name) REFERENCES channels(channel_name)
        )
    `);
});

function addChannel(channelName, callback) {
  db.run(
    "INSERT OR IGNORE INTO channels (channel_name) VALUES (?)",
    [channelName],
    callback
  );
}

function addUserChannel(userId, channelName, callback) {
  db.run(
    "INSERT INTO user_channels (user_id, channel_name) VALUES (?, ?)",
    [userId, channelName],
    callback
  );
}

function removeUserChannel(userId, channelName, callback) {
  db.run(
    "DELETE FROM user_channels WHERE user_id = ? AND channel_name = ?",
    [userId, channelName],
    callback
  );
}

function getUserChannels(userId, callback) {
  db.all(
    "SELECT channel_name FROM user_channels WHERE user_id = ?",
    [userId],
    (err, rows) => {
      if (err) {
        callback(err, null);
        return;
      }
      const channels = rows.map((row) => row.channel_name);
      callback(null, channels);
    }
  );
}

function addPostRequest(userId, channelName, postTemplate, status, callback) {
  db.run(
    "INSERT INTO post_requests (user_id, channel_name, post_template, status) VALUES (?, ?, ?, ?)",
    [userId, channelName, postTemplate, status],
    callback
  );
}

function getAllChannels(callback) {
  db.all("SELECT channel_name FROM channels", [], (err, rows) => {
    if (err) {
      callback(err, null);
      return;
    }
    const channels = rows.map((row) => row.channel_name);
    callback(null, channels);
  });
}

function getPendingRequests(userId, callback) {
  db.all(
    "SELECT channel_name, post_template, status FROM post_requests WHERE user_id = ? AND status = ?",
    [userId, "pending"],
    (err, rows) => {
      if (err) {
        callback(err, null);
        return;
      }
      callback(null, rows);
    }
  );
}

module.exports = {
  addChannel,
  addUserChannel,
  removeUserChannel,
  getUserChannels,
  addPostRequest,
  getAllChannels,
  getPendingRequests,
};
