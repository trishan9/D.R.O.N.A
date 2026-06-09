cmake_minimum_required(VERSION 3.8)
project(drona_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(std_msgs REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  # ── Messages ─────────────────────────────────────────────────────────────────
  "msg/AdvisingQuery.msg"
  "msg/AdvisingResponse.msg"
  "msg/BiasFlag.msg"
  "msg/PathwayRecommendation.msg"
  "msg/RetrievalCitation.msg"
  "msg/GestureCommand.msg"
  "msg/GestureResult.msg"
  "msg/EngagementDetection.msg"
  "msg/SessionState.msg"
  # ── Services ─────────────────────────────────────────────────────────────────
  "srv/Advise.srv"
  "srv/ExecuteGesture.srv"
  # ── Actions ──────────────────────────────────────────────────────────────────
  "action/ExecuteGesture.action"
  DEPENDENCIES builtin_interfaces std_msgs action_msgs
)

ament_package()
