"""
Filename: ui.py
Purpose: Handels all the UI functions
Author: Amitai Ben Shalom
"""

import pygame
from consts import *
from asset_loader import *
from button import Button
from laser import Laser
from datetime import datetime
import time
import math


class Ui:

    def __init__(self, screen, view_port, logger):

        self.screen = screen        
        self.view_port = view_port
        self.logger = logger
        
        self.border_line_left = convert_to_pixels("16%", self.view_port[0])
        self.border_line_right = convert_to_pixels("84%", self.view_port[0])
        self.border_line_top = convert_to_pixels("18.5%", self.view_port[1])
        self.border_line_bottom = convert_to_pixels("92%", self.view_port[1])
        self.center_inside_borders = ((self.border_line_left + self.border_line_right) // 2, (self.border_line_top + self.border_line_bottom) // 2)
        self.center = (view_port[0] // 2, view_port[1] // 2)

        cutting_area_height = self.border_line_bottom - self.border_line_top
        cutting_area_width = cutting_area_height
        self.cutting_area_size = (cutting_area_width, cutting_area_height)
        self.cutting_area_pos = (self.center_inside_borders[0] - self.cutting_area_size[0] // 2, self.center_inside_borders[1] - self.cutting_area_size[1] // 2)
        self.cutting_area_color = CUTTING_AREA_COLOR

        self.screen_to_laser_scale = [LASER_BOARD_SIZE[0] / self.cutting_area_size[0], LASER_BOARD_SIZE[1] / self.cutting_area_size[1]]  # scale from the screen to the board on arduino in mm per pixel
        self.pulse_per_pixel = [self.screen_to_laser_scale[0] / MM_PER_PULSE[0], self.screen_to_laser_scale[1] / MM_PER_PULSE[1]]  # pulse per pixel for each motor

        # dict of picture names, their sizes and position to load on screen
        PICTURES_TO_LOAD = {
            "title.png": (("38%", "17%"), ("center", 0), True),
            "frame.jpg": (("7%", None), ("4%", "15%"), False),
            "empty_drawing.jpg": (("40%", "35%"), ("center", "center"), False),
            "homming_notification.jpg": (("50%", "35%"), ("center", "center"), False),
            "preview.jpg": (("40%", "60%"), ("center", "center"), False),
        }

        BUTTONS_CONFIGURATION = {
            "draw": (("6%", None), ("89%", "22%"), ("pencil.png", "pencilPressed.png"), self.drawing_mode_on, True),
            "erase": (("6%", None), ("89%", "37%"), ("eraser.png", "eraserPressed.png"), self.erasing_mode_on, True),
            "clear": (("6%", None), ("89%", "52%"), ("garbage.png", "garbagePressed.png"), self.clear_all, False),
            "print": (("6%", None), ("89%", "75%"), ("printer.png", "printerPressed.png", "printerOff.png"), self.send_to_laser, False),
            "heart": (("7%", None), ("4%", "30%"), ("heart.jpg", "heartPressed.jpg"), self.frame_heart, True),
            "drop": (("7%", None), ("4%", "50%"), ("drop.jpg", "dropPressed.jpg"), self.frame_drop, True),
            "square": (("7%", None), ("4%", "70%"), ("square.jpg", "squarePressed.jpg"), self.frame_square, True)
        }

        self.points = []  # list of points in the current drawing, each point is (x, y) or None for stroke separation
        self.mode = DRAWING_MODE  # or ERASING_MODE
        self.frame_points = []  # list of points in the current frame
        self.frame = None  # type of the frame to draw, can be HEART_FRAME, DROP_FRAME or SQUARE_FRAME
        self.estimated_time = 0  # estimated time to complete the drawing
        self.show_estimated_time = False  # whether to show the estimated time
        self.arduino_error_message = None  # error message from Arduino to show on screen if exists, None otherwise
        self.on_screen_message = None  # message to show on screen, this is used for messages that are not related to Arduino errors, such as repeat mode message
        self.last_touch_idle = 0  # idle stopwatch
        self.empty_notification = [False, 0]  # if clicked on drawing with empty drawing, [1] = init time when showed notification
        self.homming_notification = [False, 0]  # if arduino is homming right now, [1] = init time when showed notification
        self.buttons_clicked_in_a_row = []  # for detecting hidden combos of button clicks (currently for homming)
        self.repeat = [False, 0]  # for testing laser multiple times automatcially (press R to turn on/off) - [1] = number of drawings already repeated.
        self.drawings_counter = 0  # counts how many times the laser drew - for homming after certain number of drawings (FORCE_HOMMING_AFTER_N_DRAWS)

        self.asset_loader = AssetLoader(ASSETS_DIR, PICTURES_TO_LOAD, self.view_port)
        self.buttons = self.init_buttons(BUTTONS_CONFIGURATION)
        self.laser = Laser(self.cutting_area_pos, self.cutting_area_size, logger=logger)

        self.frame_heart()

        
    def init_buttons(self, buttons_configuration):
        """
        For each button in the configuration, create a button object and add it to the buttons list
        :param buttons_configuration: dict of button names, their sizes and position to load on screen
        :return: list of button objects
        """
        buttons = {}
        for name, (size, pos, images, function, keep_pressed_image) in buttons_configuration.items():
            size = (convert_to_pixels(size[0], self.view_port[0]), convert_to_pixels(size[1], self.view_port[1]))
            pos = (convert_to_pixels(pos[0], self.view_port[0]), convert_to_pixels(pos[1], self.view_port[1]))
            button = Button(self.screen, pos, size, images, function, keep_pressed_image)
            buttons[name] = button
        return buttons
    
    def render_screen(self):
        self.screen.fill(BACKGROUND_COLOR)
        self.render_borders()
        self.render_cutting_area()
        self.asset_loader.render_all(self.screen)
        self.render_buttons()
        self.draw_lines()
        self.draw_frame()
        self.render_available_length()
        self.render_estimated_time()
        self.render_arduino_error()
        self.render_on_screen_message()
        self.render_empty_notification()
        self.render_homming_notification()
        
    def render_borders(self):
        pygame.draw.rect(self.screen, COLOR_OUTSIDE_BORDER, (0, 0, self.border_line_left, self.view_port[1]))
        pygame.draw.rect(self.screen, COLOR_OUTSIDE_BORDER, (self.border_line_right, 0, self.view_port[0] - self.border_line_right, self.view_port[1]))
        pygame.draw.rect(self.screen, COLOR_OUTSIDE_BORDER, (0, 0, self.view_port[0], self.border_line_top))
        pygame.draw.rect(self.screen, COLOR_OUTSIDE_BORDER, (0, self.border_line_bottom, self.view_port[0], self.view_port[1] - self.border_line_bottom))

    def render_cutting_area(self):
        pygame.draw.rect(self.screen, self.cutting_area_color, (self.cutting_area_pos[0], self.cutting_area_pos[1], self.cutting_area_size[0], self.cutting_area_size[1]))

    def render_buttons(self):
        for name, button in self.buttons.items():
            button.update()

        if self.mode == DRAWING_MODE:
            self.buttons["draw"].current_image = self.buttons["draw"].image_clicked
            self.buttons["erase"].current_image = self.buttons["erase"].image

        else:
            self.buttons["draw"].current_image = self.buttons["draw"].image
            self.buttons["erase"].current_image = self.buttons["erase"].image_clicked

        if self.frame == HEART_FRAME:
            self.buttons["heart"].current_image = self.buttons["heart"].image_clicked
            self.buttons["drop"].current_image = self.buttons["drop"].image
            self.buttons["square"].current_image = self.buttons["square"].image
        
        elif self.frame == DROP_FRAME:
            self.buttons["heart"].current_image = self.buttons["heart"].image
            self.buttons["drop"].current_image = self.buttons["drop"].image_clicked
            self.buttons["square"].current_image = self.buttons["square"].image

        else:
            self.buttons["heart"].current_image = self.buttons["heart"].image
            self.buttons["drop"].current_image = self.buttons["drop"].image
            self.buttons["square"].current_image = self.buttons["square"].image_clicked

        if self.laser.is_drawing() or self.homming_notification[0]:
            self.buttons["print"].current_image = self.buttons["print"].another_image

        for name, button in self.buttons.items():
            button.render()

    def render_empty_notification(self):
        if self.empty_notification[0]:
            if time.time() - self.empty_notification[1] <= 3: 
                self.asset_loader.render(self.screen, "empty_drawing")
            else:
                self.empty_notification[0] = False

    def render_homming_notification(self):
        if self.homming_notification[0]:
            if time.time() - self.homming_notification[1] <= HOMMING_TIME: 
                self.asset_loader.render(self.screen, "homming_notification")
            else:
                self.homming_notification[0] = False

    def check_idle(self):
        if time.time() - self.last_touch_idle > IDLE_TIME:
            self.points.clear()
            self.buttons_clicked_in_a_row.clear()
            self.last_touch_idle = time.time()

    def drawing_mode_on(self):
        self.buttons_clicked_in_a_row.append("draw")
        self.mode = DRAWING_MODE

    def erasing_mode_on(self):
        self.buttons_clicked_in_a_row.append("erase")
        self.mode = ERASING_MODE

    def delete_last_stroke(self):
        if not self.points:
            return
        
        idx = len(self.points) - 1
        while idx >= 0 and self.points[idx] is not None:
            idx -= 1

        self.points = self.points[:idx]  # Remove the last stroke

    def point_to_segment_distance(self, p, p1, p2):
        if p1 == p2:  # Handle the case where p1 == p2 (degenerate segment)
            return self.distance(p, p1)
    
        line_vec = (p2[0] - p1[0], p2[1] - p1[1])  # Vector from p1 to p2
        point_vec = (p[0] - p1[0], p[1] - p1[1])  # Vector from p1 to p

        line_len = self.distance(p1, p2)
        if line_len == 0:  # Prevent division by zero
            return self.distance(p, p1)

        projection = max(0, min(1, (point_vec[0] * line_vec[0] + point_vec[1] * line_vec[1]) / (line_len ** 2)))  # Project the point onto the line (scalar projection)
        closest_point = (p1[0] + projection * line_vec[0], p1[1] + projection * line_vec[1])  # Closest point on the line segment

        return self.distance(p, closest_point)

    def delete_closest_stroke(self, mouse_pos, threshold=MIN_DISTANCE_BETWEEN_POINTS):
        closest_stroke = None
        min_distance = float('inf')
        closest_stroke_start_idx = -1
        closest_stroke_end_idx = -1

        current_stroke = []
        for idx, point in enumerate(self.points):
            if point is None:
                if current_stroke:
                    for i in range(len(current_stroke) - 1):
                        p1 = current_stroke[i]
                        p2 = current_stroke[i + 1]
                        dist = self.point_to_segment_distance(mouse_pos, p1, p2)
                        if dist < min_distance:
                            min_distance = dist
                            closest_stroke = current_stroke
                            closest_stroke_start_idx = self.points.index(current_stroke[0])
                            closest_stroke_end_idx = self.points.index(current_stroke[-1]) + 1
                current_stroke = []
            else:
                current_stroke.append(point)

        if closest_stroke and min_distance <= threshold:
            del self.points[closest_stroke_start_idx:closest_stroke_end_idx]

    def clear_all(self):
        self.buttons_clicked_in_a_row.append("clear")
        self.points.clear()

    def repeat_mode_on(self):
        self.repeat = [True, 0]
        self.on_screen_message = REPEAT_MODE_ON_MESSAGE

    def repeat_mode_off(self):
        self.repeat = [False, 0]
        self.on_screen_message = None

    def homming(self, alert=True):
        if self.laser.exist():
            self.logger.info("Sent homming command to laser")

            if alert:
                self.homming_notification[0] = True
                self.homming_notification[1] = time.time()

            self.laser.send_values("RESET")
            self.laser.end_drawing()
            self.show_estimated_time = False

    def detect_hidden_homming_combo(self):
        # if user pressed on combo below in a row, send homming command to laser
        combo = ["clear", "erase", "draw", "clear", "erase", "draw", "clear", "erase", "draw"]
        if len(self.buttons_clicked_in_a_row) < len(combo):
            return
        
        if self.buttons_clicked_in_a_row[-len(combo):] == combo:
            self.logger.info("Detected homming combo, sending homming command to laser...")
            self.homming()
            self.buttons_clicked_in_a_row = []  # reset the button combo tracker

    def send_to_laser(self, save_image=True, alert_empty=True):
        if not self.laser.exist():
            self.logger.error("Error: No Arduino is connected, skipping")
            return
        
        if self.homming_notification[0]:  # if currently homming, don't allow sending to laser
            self.logger.error("Clicked on print button while homming, skipping")
            return
            
        if self.laser.is_drawing():
            return
        
        if alert_empty and len(self.points) == 0:
            self.empty_notification = [True, time.time()] 
            self.logger.info("Clicked on print button with empty drawing, skipping")
            return

        if save_image:
            self.save_drawing_as_image()
        
        self.estimated_time = self.calc_estimated_time()
        self.show_estimated_time = True
        self.laser.init_drawing(self.points.copy(), self.frame_points.copy())

    def save_drawing_as_image(self):
        os.makedirs(DRAWINGS_DIR, exist_ok=True)  # create the drawings folder if it doesn't exist
        self.draw_lines()
        self.draw_frame()
        x, y = self.cutting_area_pos
        w, h = self.cutting_area_size
        filename = os.path.join(DRAWINGS_DIR, datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '.png')
        sub_surface = self.screen.subsurface(pygame.Rect(x, y, w, h)).copy()
        pygame.image.save(sub_surface, filename)    

    def handle_laser(self):
        if not self.laser.is_drawing():
            try:
                if self.laser.arduino.in_waiting:
                    response = self.laser.arduino.readline().strip()
                    self.logger.info(f"Arduino sent: {response}")

                    if response == b"READY":
                        self.arduino_error_message = None
                        self.laser.send_initial_parameters()  # wait until arduino sends first message
                    
                    else:
                        # this is not expected, show error
                        self.logger.error(f"Unexpected response from Arduino!!!: {response}")
                        self.arduino_error_message = ERROR_UNEXPECTED_ARDUINO_RESPONSE

                if self.repeat[0]:
                    time.sleep(1)  # delay to make sure everything is stable
                    self.send_to_laser(save_image=False, alert_empty=False)
                    self.on_screen_message = REPEAT_MODE_ON_MESSAGE + f" Completed: {self.repeat[1]}"
                    self.repeat[1] += 1

            except:
                self.arduino_error_message = ERROR_LASER_DISCONNECTED
                self.laser.arduino = None

            finally:
                return
        
        # if got to here - this means laser is currently drawing, check if it finished or if there is an error
        status = self.laser.check_on_laser()

        if status == "NO_ARDUINO":
            return

        if status != "DRAWING":  # this includes "RESET", "SUCCESS", "ERROR_UNEXPECTED_RESPONSE", "ERROR_ARDUINO_DISCONNECTED"
            self.laser.end_drawing()
            self.show_estimated_time = False
            self.arduino_error_message = None

            if status == "SUCCESS":
                self.drawings_counter += 1
                if self.drawings_counter >= FORCE_HOMMING_AFTER_N_DRAWS:
                    self.logger.info(f"Automatically sending homming command after {FORCE_HOMMING_AFTER_N_DRAWS} drawings...")
                    self.homming()
                    self.drawings_counter = 0

            if status == "RESET":
                self.logger.error("Timeout waiting for Arduino. Stopping transmission.")
            
            elif status == "ERROR_ARDUINO_DISCONNECTED":
                self.logger.error("Arduino disconnected! Reconnect it and restart program")
                self.arduino_error_message = ERROR_LASER_DISCONNECTED

            elif status == "ERROR_UNEXPECTED_RESPONSE":
                self.logger.error("Unexpected response from Arduino. Stopping transmission.")
                self.arduino_error_message = ERROR_UNEXPECTED_ARDUINO_RESPONSE

            return

        self.arduino_error_message = None
        

    def render_arduino_error(self):
        if self.arduino_error_message is None:
            return
        
        font = pygame.font.SysFont(None, int(0.025 * self.view_port[0]))
        text_color = RED
        text = font.render(self.arduino_error_message, True, text_color)
        self.screen.blit(text, (self.border_line_left, self.border_line_top))

    def render_on_screen_message(self):
        if self.on_screen_message is None:
            return
        
        font = pygame.font.SysFont(None, int(0.02 * self.view_port[0]))
        text_color = DARK_GREEN
        text = font.render(self.on_screen_message, True, text_color)
        self.screen.blit(text, (self.border_line_left, self.border_line_top + 30))

    def frame_heart(self):
        self.buttons_clicked_in_a_row.append("heart")
        self.frame = HEART_FRAME
        self.frame_points.clear()
        
        with open(os.path.join(FRAMES_DIR, "heart.txt"), 'r') as f:
            lines = [line.strip() for line in f if not line.startswith("#")]

            relative_width = int(lines[0])
            relative_height = int(lines[1])
            list_points = eval(lines[2])

            # scale frame to view port
            for i, point in enumerate(list_points):
                if point is not None:
                    x, y = point
                    list_points[i] = (x / relative_width * self.view_port[0] + self.center_inside_borders[0] - self.center[0],
                                       y / relative_height * self.view_port[1]  + self.center_inside_borders[1] - self.center[1])

            self.frame_points = list_points


    def frame_drop(self):
        self.buttons_clicked_in_a_row.append("drop")
        self.frame = DROP_FRAME
        self.frame_points.clear()
        
        with open(os.path.join(FRAMES_DIR, "drop.txt"), 'r') as f:
            lines = [line.strip() for line in f if not line.startswith("#")]

            relative_width = int(lines[0])
            relative_height = int(lines[1])
            list_points = eval(lines[2])

            # scale frame to view port
            for i, point in enumerate(list_points):
                if point is not None:
                    x, y = point
                    list_points[i] = (x / relative_width * self.view_port[0] + self.center_inside_borders[0] - self.center[0],
                                       y / relative_height * self.view_port[1]  + self.center_inside_borders[1] - self.center[1])

            self.frame_points = list_points

    def frame_square(self):
        self.buttons_clicked_in_a_row.append("square")
        self.frame = SQUARE_FRAME
        self.frame_points.clear()
        
        with open(os.path.join(FRAMES_DIR, "square.txt"), 'r') as f:
            lines = [line.strip() for line in f if not line.startswith("#")]

            relative_width = int(lines[0])
            relative_height = int(lines[1])
            list_points = eval(lines[2])

            # scale frame to view port
            for i, point in enumerate(list_points):
                if point is not None:
                    x, y = point
                    list_points[i] = (x / relative_width * self.view_port[0] + self.center_inside_borders[0] - self.center[0],
                                       y / relative_height * self.view_port[1]  + self.center_inside_borders[1] - self.center[1])

            self.frame_points = list_points

    def distance(self, p1, p2):
        return math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    
    def in_border(self, pos):
        return self.border_line_left < pos[0] < self.border_line_right and self.border_line_top < pos[1] < self.border_line_bottom

    def add_point(self, pos):
        if (not self.points or self.points[-1] is None or self.distance(self.points[-1], pos) >= MIN_DISTANCE_BETWEEN_POINTS):
            if self.in_border(pos) and self.total_drawing_length() <  MAX_LENGTH:
                self.points.append(pos)
                self.buttons_clicked_in_a_row.clear()  # reset the button combo tracker if user is drawing
            
            elif self.points and self.points[-1] is not None:
                self.points.append(None)
    
    def end_stroke(self):
        if self.mode == DRAWING_MODE:
            if self.points and self.points[-1] is not None:
                self.points.append(None)

    def total_drawing_length(self):
        total_length = 0
        current_stroke = []

        for point in self.points:
            if point is None:
                if len(current_stroke) > 1:
                    for i in range(len(current_stroke) - 1):
                        total_length += self.distance(current_stroke[i], current_stroke[i + 1])
                current_stroke = []
            else:
                current_stroke.append(point)

        if len(current_stroke) > 1:
            for i in range(len(current_stroke) - 1):
                total_length += self.distance(current_stroke[i], current_stroke[i + 1])


        return total_length

    def handle_point(self, mouse_pos):
        if self.mode == DRAWING_MODE:
            self.add_point(mouse_pos)
        else:
            self.delete_closest_stroke(mouse_pos)

    def draw_lines(self):
        last_point = None
        for point in self.points:
            
            if point is None:
                last_point = None
                continue
            
            if last_point is not None:
                pygame.draw.line(self.screen, DRAWING_COLOR, last_point, point, DRAWING_WIDTH)
            
            last_point = point

    def draw_frame(self):
        last_point = None
        for point in self.frame_points:
            
            if point is None:
                last_point = None
                continue
            
            if last_point is not None:
                pygame.draw.line(self.screen, FRAME_COLOR, last_point, point, FRAME_WIDTH)
            
            last_point = point

    def render_available_length(self, width="12%", height="3%"):
        available_length_precentage = max(0, min(100, int((1 - (self.total_drawing_length() / MAX_LENGTH)) * 100)))

        width = convert_to_pixels(width, self.view_port[0])
        height = convert_to_pixels(height, self.view_port[1])
        font = pygame.font.SysFont(None, int(0.03 * self.view_port[0]))
        text_color = BLACK
        rect_color = THE_RED_THAT_IS_ON_THE_BUTTONS
        bg_color = BLACK
        text = font.render(f"{available_length_precentage}%", True, text_color)
        self.screen.blit(text, ((self.border_line_right + (self.view_port[0] - self.border_line_right) // 2) - text.get_width() // 2, (self.border_line_top - text.get_height() - height) // 2))
        pygame.draw.rect(self.screen, bg_color, ((self.border_line_right + (self.view_port[0] - self.border_line_right) // 2) - width // 2, (self.border_line_top - height + text.get_height()) // 2, width, height))
        pygame.draw.rect(self.screen, rect_color, ((self.border_line_right + (self.view_port[0] - self.border_line_right) // 2) - width // 2, (self.border_line_top - height + text.get_height()) // 2, width * (available_length_precentage / 100), height))

    def render_estimated_time(self):
        if not self.show_estimated_time:
            return
        font = pygame.font.SysFont(None, int(0.03 * self.view_port[0]))
        text_color = BLACK
        text = font.render(f"{max(self.estimated_time - time.time() + self.laser.drawing_start_time, 0):.1f}", True, text_color)
        self.screen.blit(text, (self.buttons["print"].pos[0] + self.buttons["print"].size[0] // 2 - text.get_width() // 2, self.buttons["print"].pos[1] + self.buttons["print"].size[1] + 5))

    def calc_estimated_time(self):

        # distance is NOT sqrt of sum of squares because laser is going in zigzag and not in a straight line, the time is dictated by the longer axis travel
        def distance_by_laser(p1, p2):
            return max(abs(p1[0] - p2[0]), abs(p1[1] - p2[1]))

        estimated_time = 0
        last_point = [self.center_inside_borders[0] - self.cutting_area_size[0] // 2, self.center_inside_borders[1] - self.cutting_area_size[1] // 2]
        current_stroke = []
        current_stoke_length = 0

        for point in self.points:
            if point is None:
                if len(current_stroke) > 1:
                    for i in range(len(current_stroke) - 1):
                        current_stoke_length += distance_by_laser(current_stroke[i], current_stroke[i + 1])
                    estimated_time += distance_by_laser(last_point, current_stroke[0]) * self.pulse_per_pixel[0] * LASER_OFF_RATE / 1000
                    estimated_time += current_stoke_length * self.pulse_per_pixel[0] * LASER_ON_RATE / 1000
                    last_point = current_stroke[-1]
                current_stroke = []
                current_stoke_length = 0
            else:
                current_stroke.append(point)

        if len(current_stroke) > 1:
            for i in range(len(current_stroke) - 1):
                current_stoke_length += distance_by_laser(current_stroke[i], current_stroke[i + 1])
            estimated_time += distance_by_laser(last_point, current_stroke[0]) * self.pulse_per_pixel[0] * LASER_OFF_RATE / 1000
            estimated_time += current_stoke_length * self.pulse_per_pixel[0] * LASER_ON_RATE / 1000
            last_point = current_stroke[-1]
        
        # same with frame:
        current_stroke = []
        current_stoke_length = 0

        for point in self.frame_points:
            if point is None:
                if len(current_stroke) > 1:
                    for i in range(len(current_stroke) - 1):
                        current_stoke_length += distance_by_laser(current_stroke[i], current_stroke[i + 1])
                    estimated_time += distance_by_laser(last_point, current_stroke[0]) * self.pulse_per_pixel[0] * LASER_OFF_RATE / 1000
                    estimated_time += current_stoke_length * self.pulse_per_pixel[0] * FRAME_RATE / 1000
                    last_point = current_stroke[-1]
                current_stroke = []
                current_stoke_length = 0
            else:
                current_stroke.append(point)

        if len(current_stroke) > 1:
            for i in range(len(current_stroke) - 1):
                current_stoke_length += distance_by_laser(current_stroke[i], current_stroke[i + 1])
            estimated_time += distance_by_laser(last_point, current_stroke[0]) * self.pulse_per_pixel[0] * LASER_OFF_RATE / 1000
            estimated_time += current_stoke_length * self.pulse_per_pixel[0] * FRAME_RATE / 1000
            last_point = current_stroke[-1]

        return estimated_time