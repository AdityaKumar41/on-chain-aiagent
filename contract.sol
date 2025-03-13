// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract AIAgent {
    struct Task {
        uint256 id;
        string topic;
        string result;
        address requester;
    }

    uint256 public taskCounter;
    mapping(uint256 => Task) public tasks;

    event TaskCreated(uint256 id, string topic, address requester);
    event TaskCompleted(uint256 id, string result);

    function createTask(string memory _topic) public {
        taskCounter++;
        tasks[taskCounter] = Task(taskCounter, _topic, "", msg.sender);
        emit TaskCreated(taskCounter, _topic, msg.sender);
    }

    function completeTask(uint256 _id, string memory _result) public {
        require(tasks[_id].id != 0, "Task does not exist");
        tasks[_id].result = _result;
        emit TaskCompleted(_id, _result);
    }

    function getTask(uint256 _id) public view returns (Task memory) {
        return tasks[_id];
    }
}
