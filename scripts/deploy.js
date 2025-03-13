const { ethers, run, network } = require("hardhat");

async function main() {
  // Deploy the AIAgent contract
  console.log("Deploying AIAgent contract...");
  const AIAgent = await ethers.getContractFactory("AIAgent");
  const aiAgent = await AIAgent.deploy();

  await aiAgent.waitForDeployment();
  const address = await aiAgent.getAddress();
  console.log(`AIAgent deployed to: ${address}`);

  // Log network information
  console.log(`Deployed on network: ${network.name}`);

  // Avalanche Fuji specific logging
  if (network.name === "fuji" || network.config.chainId === 43113) {
    console.log("Deployed on Avalanche Fuji Testnet!");
    console.log(
      "View contract on Snowtrace: https://testnet.snowtrace.io/address/" +
        address
    );

    console.log(
      "NOTE: Contract verification is skipped as no API key is provided."
    );
    console.log("To verify manually, you can use the following details:");
    console.log("Contract Address:", address);
    console.log("Contract Source:", "AIAgent.sol");
  }

  // Create a sample task to test functionality
  console.log("Creating a sample task...");
  const tx = await aiAgent.createTask("Sample AI task");
  await tx.wait(1);
  console.log("Sample task created!");

  // Get the task details
  const task = await aiAgent.getTask(1);
  console.log("Task details:", {
    id: task.id.toString(),
    topic: task.topic,
    result: task.result,
    requester: task.requester,
  });
}

// Execute the deployment
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
