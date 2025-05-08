require("dotenv").config();
const TelegramBot = require("node-telegram-bot-api");
const express = require("express");
const bodyParser = require("body-parser");
const db = require("./database"); // Импортируем модуль для работы с базой данных

const token = process.env.TELEGRAM_BOT_TOKEN;
const bot = new TelegramBot(token, { polling: true });
const ADMIN_USER_ID = parseInt(process.env.ADMIN_USER_ID);
const postRequests = {}; // Хранение запросов на взаимные посты

// Функция для проверки прав на отправку сообщений
const checkIfBotCanPostMessages = async (chatId) => {
  try {
    // Попытка отправить тестовое сообщение
    const testMessage =
      "Тестовое сообщение для проверки прав на отправку сообщений";
    await bot.sendMessage(chatId, testMessage);
    console.log(`Bot can post messages in ${chatId}`);
    return true;
  } catch (error) {
    console.error(`Error sending message to ${chatId}:`, error.message);
    return false;
  }
};

// Команды бота
bot.onText(/\/start/, (msg) => {
  bot.sendMessage(
    msg.chat.id,
    "Привет! Я бот для взаимного обмена постами между каналами."
  );
});

bot.onText(/\/stats/, async (msg) => {
  const userId = msg.from.id;
  const username = msg.from.username;

  db.getUserChannels(userId, (err, userChannels) => {
    if (err) {
      bot.sendMessage(msg.chat.id, "Произошла ошибка при получении данных.");
      return;
    }

    if (!userChannels || userChannels.length === 0) {
      bot.sendMessage(
        msg.chat.id,
        "У вас нет привязанных каналов. Используйте /addchannel @channel_name для добавления канала."
      );
      return;
    }

    let response = `Личный кабинет для @${username}:\nПривязанные каналы:\n`;
    userChannels.forEach((channel, index) => {
      response += `${index + 1}. @${channel}\n`;
    });

    response += "\nДобавить канал: /addchannel @channel_name\n";
    response += "Удалить канал: /removechannel @channel_name\n";
    response += "Создать запрос на взаимный пост: /createpost\n";

    bot.sendMessage(msg.chat.id, response);
  });
});

bot.onText(/\/addchannel (.+)/, async (msg, match) => {
  const userId = msg.from.id;
  const channelName = match[1].replace("@", "");

  try {
    const chatId = `@${channelName}`;
    const canPostMessages = await checkIfBotCanPostMessages(chatId);

    if (canPostMessages) {
      db.addUserChannel(userId, channelName, (err) => {
        if (err) {
          bot.sendMessage(msg.chat.id, "Ошибка при добавлении канала.");
          return;
        }
        bot.sendMessage(
          msg.chat.id,
          `Канал @${channelName} привязан к вашему аккаунту.`
        );
      });
    } else {
      bot.sendMessage(
        msg.chat.id,
        `Пожалуйста, убедитесь, что я имею право "Отправлять сообщения" в канале @${channelName}.`
      );
    }
  } catch (error) {
    bot.sendMessage(
      msg.chat.id,
      `Ошибка при добавлении канала: ${error.message}`
    );
  }
});

bot.onText(/\/removechannel (.+)/, (msg, match) => {
  const userId = msg.from.id;
  const channelName = match[1].replace("@", "");

  db.removeUserChannel(userId, channelName, (err) => {
    if (err) {
      bot.sendMessage(msg.chat.id, "Ошибка при удалении канала.");
      return;
    }
    bot.sendMessage(
      msg.chat.id,
      `Канал @${channelName} отвязан от вашего аккаунта.`
    );
  });
});

bot.onText(/\/createpost/, (msg) => {
  const userId = msg.from.id;

  db.getUserChannels(userId, (err, userChannels) => {
    if (err) {
      bot.sendMessage(msg.chat.id, "Ошибка при получении ваших каналов.");
      return;
    }

    if (!userChannels || userChannels.length === 0) {
      bot.sendMessage(
        msg.chat.id,
        "У вас нет привязанных каналов для создания запроса. Привяжите канал с помощью /addchannel @channel_name."
      );
      return;
    }

    const keyboard = userChannels.map((channel) => [
      { text: `@${channel}`, callback_data: `select_channel_${channel}` },
    ]);

    const opts = {
      reply_markup: {
        inline_keyboard: keyboard,
      },
    };
    bot.sendMessage(msg.chat.id, "Выберите канал для взаимного поста:", opts);
  });
});

bot.on("callback_query", async (query) => {
  const chatId = query.message.chat.id;
  const data = query.data;
  const userId = query.from.id;

  if (data.startsWith("select_channel_")) {
    const channelName = data.substring("select_channel_".length);
    postRequests[userId] = { channelName, postTemplate: null };
    bot.sendMessage(
      chatId,
      `Вы выбрали канал @${channelName}. Пожалуйста, отправьте шаблон поста.`
    );
    bot.deleteMessage(chatId, query.message.message_id);
  } else if (data.startsWith("confirm_") || data.startsWith("decline_")) {
    const [action, channelName, requesterId] = data.split("_", 3);
    if (action === "confirm") {
      // Обработка подтверждения
      const postTemplate = postRequests[requesterId]?.postTemplate;
      if (postTemplate) {
        const responseMessage = `Ваш пост от канала @${channelName}:\n\n${postTemplate}`;
        bot.sendMessage(`@${channelName}`, responseMessage);
        bot.sendMessage(
          requesterId,
          `Ваш запрос на взаимный пост был принят и опубликован в @${channelName}.`
        );
        db.updatePostRequest(
          requesterId,
          channelName,
          postTemplate,
          "confirmed",
          (err) => {
            if (err) {
              console.error("Ошибка при обновлении запроса:", err);
            }
          }
        );
      }
    } else {
      bot.sendMessage(
        requesterId,
        `Ваш запрос на взаимный пост от канала @${channelName} был отклонен.`
      );
    }
    bot.deleteMessage(chatId, query.message.message_id);
    delete postRequests[requesterId];
  }
});

bot.on("message", async (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text;

  if (postRequests[chatId]) {
    const { channelName } = postRequests[chatId];
    postRequests[chatId].postTemplate = text;

    const keyboard = [
      [
        {
          text: "Подтвердить",
          callback_data: `confirm_${channelName}_${chatId}`,
        },
      ],
      [
        {
          text: "Отклонить",
          callback_data: `decline_${channelName}_${chatId}`,
        },
      ],
    ];
    const opts = {
      reply_markup: {
        inline_keyboard: keyboard,
      },
    };

    bot.sendMessage(
      chatId,
      `Получен запрос на взаимный пост от канала @${await getChannelNameByUserId(
        chatId
      )}. Шаблон поста:\n\n${text}\n\nПодтвердите или отклоните запрос.`,
      opts
    );
    db.addPostRequest(chatId, channelName, text, "pending", (err) => {
      if (err) {
        console.error("Ошибка при добавлении запроса на пост:", err);
      }
    });
  }
});

async function getChannelNameByUserId(userId) {
  return new Promise((resolve, reject) => {
    db.getUserChannels(userId, (err, userChannels) => {
      if (err) {
        console.error("Ошибка при получении канала пользователя:", err);
        reject("Неизвестный канал");
      }
      if (userChannels.length) {
        resolve(userChannels[0]);
      } else {
        resolve("Неизвестный канал");
      }
    });
  });
}

// Запуск сервера
const app = express();
app.use(bodyParser.json());

app.get("/channels/:userId", (req, res) => {
  const userId = req.params.userId;
  db.getUserChannels(userId, (err, userChannels) => {
    if (err) {
      res.status(500).send("Ошибка при получении данных.");
      return;
    }
    res.json(userChannels);
  });
});

app.post("/removeChannel", (req, res) => {
  const { userId, channel } = req.body;
  db.removeUserChannel(userId, channel, (err) => {
    if (err) {
      res.status(500).send("Ошибка при удалении канала.");
      return;
    }
    res.send("Канал удален");
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

// Запуск бота
bot.on("polling_error", console.log);

console.log("Bot and server are running...");
