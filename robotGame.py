import sys, math
from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PyQt5.QtGui import QPainter, QColor, QPixmap, QVector2D, QBrush, QFont, QGuiApplication
from PyQt5.QtCore import Qt, QBasicTimer, QPointF, QElapsedTimer, pyqtSignal, QRectF, QDateTime, QObject

from levelLoader import LevelLoader, Tile
import robots
import control
from arsenal import Handgun, Shotgun, GrenadeLauncher

DEBUG_LINES = False
GOD_MODE = False
DUEL_MODE = True

#Window options

WINDOW_SIZE = 1000
START_WINDOW_X_POS = 100
START_WINDOW_Y_POS = 50
WINDOW_TITLE = "Cooles Spiel"

# Game constants

NUMBER_OF_TILES = 100
WALL_TILE_COLOR = QColor(0, 0, 0)
FLOOR_TILE_COLOR = QColor(255, 255, 255)
TILE_SIZE = 10

FPS = 30
MILLISECONDS_PER_SECOND = 1000
TICK_INTERVALL = int(MILLISECONDS_PER_SECOND / FPS)

class RobotGame(QWidget):

    keysPressedSignal = pyqtSignal(list)

    def __init__(self):
        super().__init__()

        # Load level data from file
        if DUEL_MODE:
            self.levelMatrix, self.obstacles = LevelLoader.loadLevel('arena.txt')
            self.spawnPlayer1 = QVector2D(50, 500)
            self.spawnPlayer2 = QVector2D(950, 500)
        else:
            self.levelMatrix, self.obstacles = LevelLoader.loadLevel('level2.txt')
            self.spawnPlayer1 = QVector2D(550, 550)
            self.spawnPlayer2 = QVector2D(450, 450)

        self.initUI()
        self.initTextures()
        self.initRobots()
        self.initTimer()

        self.keysPressed = []
        self.keysPressed2 = []

    def initTextures(self):

        self.tileTextures = {tileEnum : QPixmap('textures/' + tileName + '.png') for tileName, tileEnum in Tile.__members__.items()}

    def initUI(self):

        self.setGeometry(START_WINDOW_X_POS, START_WINDOW_Y_POS, WINDOW_SIZE, WINDOW_SIZE)
        self.setWindowTitle(WINDOW_TITLE)
        self.show()

    def initTimer(self):

        self.gameTimer = QBasicTimer()
        self.gameTimer.start(TICK_INTERVALL, self)

        # For deltaTime
        self.elapsedTimer = QElapsedTimer()
        self.elapsedTimer.start()
        self.previous = 0
        self.tickCounter = 0

    def initRobots(self):

        self.robots = {}

        player1 = robots.TestRobot(1, self.spawnPlayer1.x(), self.spawnPlayer1.y(), control.PlayerController)
        player2 = robots.TestRobot(2, self.spawnPlayer2.x(), self.spawnPlayer2.y(), control.XboxController)

        if GOD_MODE:
            handgun = Handgun(player1, 500, 0.1, 80)
            shotgun = Shotgun(player1, 200, 0.1, 10, 20)
            grenade = GrenadeLauncher(player1, 200, 0.1, 10, 100)
            handgun_player_2 = Handgun(player2, 500, 0.1, 80)
            shotgun_player_2 = Shotgun(player2, 200, 0.1, 10, 20)
            grenade_player_2 = GrenadeLauncher(player2, 200, 0.1, 10, 100)
        else:
            handgun = Handgun(player1, 500, 1, 80)
            shotgun = Shotgun(player1, 200, 2, 10, 20)
            grenade = GrenadeLauncher(player1, 200, 3, 10, 100)
            handgun_player_2 = Handgun(player2, 500, 1, 80)
            shotgun_player_2 = Shotgun(player2, 200, 2, 10, 20)
            grenade_player_2 = GrenadeLauncher(player2, 200, 3, 10, 100)

        handgun.hitSignal.connect(self.hitSignalSlot)
        shotgun.hitSignal.connect(self.hitSignalSlot)
        grenade.hitSignal.connect(self.hitSignalSlot)
        handgun_player_2.hitSignal.connect(self.hitSignalSlot)
        shotgun_player_2.hitSignal.connect(self.hitSignalSlot)
        grenade_player_2.hitSignal.connect(self.hitSignalSlot)

        player1.equipWithGuns(handgun, shotgun, grenade)
        player2.equipWithGuns(handgun_player_2, shotgun_player_2, grenade_player_2)

        self.keysPressedSignal.connect(player1.controller.keysPressedSlot)

        if DUEL_MODE:
            self.robots = {robot.id : robot for robot in [player1, player2]}
        else:

            chaser1 = robots.ChaserRobot(3, 200, 500, 1, 200, control.ChaseDirectlyController)
            handgun1 = Handgun(chaser1, 500, 2, 80)
            chaser1.equipWithGuns(handgun1)
            handgun1.hitSignal.connect(self.hitSignalSlot)

            chaser2 = robots.ChaserRobot(4, 500, 200, 1, 200, control.ChasePredictController)
            handgun2 = Handgun(chaser2, 500, 2, 80)
            chaser2.equipWithGuns(handgun2)
            handgun2.hitSignal.connect(self.hitSignalSlot)

            chaser3 = robots.ChaserRobot(5, 800, 500, 1, 200, control.ChaseGuardController)
            handgun3 = Handgun(chaser3, 500, 2, 80)
            chaser3.equipWithGuns(handgun3)
            handgun3.hitSignal.connect(self.hitSignalSlot)

            self.robots = {robot.id : robot for robot in [player1, player2, chaser1, chaser2, chaser3]}

        for robot in self.robots.values():

            robot.connectSignals()

            # Tell the controller the specs of the robot (a_max and a_alpha_max)
            robot.robotSpecsSignal.emit(robot.a_max, robot.a_alpha_max, robot.v_max, robot.v_alpha_max)

            # Start the controller threads
            robot.controller.start()

    def paintEvent(self, event):

        qp = QPainter()
        qp.begin(self)
        self.drawTiles(event, qp)
        for robot in self.robots.values():
            robot.draw(qp)

        if DEBUG_LINES:
            self.drawObstaclesDebugLines(qp)
            for robot in self.robots.values():
                robot.drawDebugLines(qp)

        qp.end()

    def drawTiles(self, event, qp):

        qp.setPen(Qt.NoPen)
        for row in range(NUMBER_OF_TILES):
            for column in range(NUMBER_OF_TILES):
                tile = self.levelMatrix[row][column]
                texture = self.tileTextures[tile]
                qp.drawPixmap(column*TILE_SIZE, row*TILE_SIZE, texture)

    def drawObstaclesDebugLines(self, qp):
        qp.setPen(Qt.blue)
        qp.setBrush(QBrush(Qt.NoBrush))
        for rect in self.obstacles:
            qp.drawRect(rect)

    def timerEvent(self, event):

        self.tickCounter += 1

        elapsed = self.elapsedTimer.elapsed()
        deltaTimeMillis = elapsed - self.previous
        deltaTime = deltaTimeMillis / MILLISECONDS_PER_SECOND

        if deltaTime < 0.5:

            # Update robots
            for robot in self.robots.values():
                robot.update(deltaTime, self.levelMatrix, self.robots)

            # send positions data every 5th tick
            if self.tickCounter % 5 == 0:
                for robot in self.robots.values():
                    self.emitRobotSensorData(robot)

            # send key information to player controller
            self.keysPressedSignal.emit(self.keysPressed)

            # Update visuals
            self.update()


        self.previous = elapsed


    def emitRobotSensorData(self, robot):

        cone = robot.view_cone()
        robotsInView = {}
        timestamp = QDateTime.currentMSecsSinceEpoch()

        # Special case for runner robot: He sees everything:
        if isinstance(robot, robots.RunnerRobot):
            ids = self.robots.keys()
            wallsInView = self.obstacles
        else:
            # Get ids of all robots that are in view, i.e. that intersect with the view cone
            ids = filter(lambda id : cone.intersects(self.robots[id].shape()), self.robots)
            wallsInView = filter(cone.intersects, self.obstacles)

        for id in ids:
            other = self.robots[id]
            dist = (robot.pos - other.pos).length()
            angle = math.degrees(math.atan2(other.y - robot.y, other.x - robot.x))
            robotsInView[id] = {'x' : other.x,
                                'y' : other.y,
                                'id': other.id,
                                'pos' : QVector2D(other.x, other.y),
                                'dist' : dist,
                                'angle' : angle,
                                'timestamp' : timestamp}

        robot.robotsInViewSignal.emit(robotsInView)
        robot.wallsInViewSignal.emit(list(wallsInView))

    def keyPressEvent(self, event):
        self.keysPressed.append(event.key())

    def keyReleaseEvent(self, event):
        self.keysPressed.remove(event.key())

    ### Slots

    # Will be called whenever a robot kills another robot. id is the id of the robots that has to be killed
    def hitSignalSlot(self, id, damage):
        self.robots[id].dealDamage(damage)

if __name__ == '__main__':

    app = QApplication(sys.argv)

    game = RobotGame()

    sys.exit(app.exec_())
