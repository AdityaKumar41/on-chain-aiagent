require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

module.exports = {
  solidity: "0.8.20",
  networks: {
    fuji: {
      url: process.env.AVALANCHE_FUJI_RPC,
      accounts: [process.env.PRIVATE_KEY],
    },
  },
};
