// channels.js
let userChannels = {};

const addUserChannel = (userId, username, channel) => {
  if (!userChannels[userId]) {
    userChannels[userId] = { username: username, channels: [] };
  }
  userChannels[userId].channels.push(channel);
};

const removeUserChannel = (userId, channel) => {
  if (userChannels[userId]) {
    userChannels[userId].channels = userChannels[userId].channels.filter(
      (ch) => ch !== channel
    );
  }
};

const getUserChannels = (userId) => {
  return userChannels[userId] || null;
};

module.exports = {
  addUserChannel,
  removeUserChannel,
  getUserChannels,
};
